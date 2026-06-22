"""
PropIQ — Subscription & Payment Module
Gestion des plans Free/Premium + Intégration STRIPE (International).
Supporte aussi Konnect (Tunisie) via config.
"""

import httpx
import logging
import stripe
from datetime import datetime, date
from typing import Optional

from firebase_admin import firestore
from fastapi import HTTPException

from config import (
    PLANS,
    PAYMENT_PROVIDER,
    # Konnect Config
    KONNECT_API_KEY,
    KONNECT_WALLET_ID,
    KONNECT_SUCCESS_URL,
    KONNECT_FAIL_URL,
    KONNECT_WEBHOOK_URL,
    KONNECT_API_BASE,
    # Stripe Config (à ajouter dans config.py)
    STRIPE_SECRET_KEY,
    STRIPE_SUCCESS_URL,
    STRIPE_CANCEL_URL,
    # Firestore Config
    FIRESTORE_USERS_COLLECTION,
    FIRESTORE_USAGE_SUBCOLLECTION,
)

# Configuration de Stripe
if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

logger = logging.getLogger(__name__)

# ============================================================
# FIRESTORE CLIENT
# ============================================================


def get_firestore():
    return firestore.client()


# ============================================================
# HELPERS — Lecture / écriture Firestore (Inchangés)
# ============================================================
def get_user_plan(uid: str) -> str:
    db = get_firestore()
    doc = db.collection(FIRESTORE_USERS_COLLECTION).document(uid).get()
    if doc.exists:
        return doc.to_dict().get("plan", "free")
    return "free"


def set_user_plan(uid: str, plan: str, payment_ref: Optional[str] = None):
    db = get_firestore()
    ref = db.collection(FIRESTORE_USERS_COLLECTION).document(uid)
    data = {
        "plan": plan,
        "updated_at": datetime.utcnow().isoformat(),
    }
    if payment_ref:
        data["last_payment_ref"] = payment_ref
    ref.set(data, merge=True)
    logger.info(f"[Subscription] ✅ Plan mis à jour — uid={uid} | plan={plan}")


def get_today_usage(uid: str) -> dict:
    db = get_firestore()
    today = date.today().isoformat()
    doc = (
        db.collection(FIRESTORE_USERS_COLLECTION)
        .document(uid)
        .collection(FIRESTORE_USAGE_SUBCOLLECTION)
        .document(today)
        .get()
    )
    if doc.exists:
        return doc.to_dict()
    return {"requests": 0, "images": 0, "pdfs": 0}


def increment_usage(uid: str, usage_type: str):
    db = get_firestore()
    today = date.today().isoformat()
    ref = (
        db.collection(FIRESTORE_USERS_COLLECTION)
        .document(uid)
        .collection(FIRESTORE_USAGE_SUBCOLLECTION)
        .document(today)
    )
    ref.set({usage_type: firestore.Increment(1)}, merge=True)


# ============================================================
# VÉRIFICATION DES QUOTAS (Inchangés)
# ============================================================
def check_quota(uid: str, usage_type: str) -> dict:
    plan = get_user_plan(uid)
    limits = PLANS[plan]
    limit_key = f"{usage_type}_per_day"
    limit = limits.get(limit_key, 0)
    usage = get_today_usage(uid)
    used = usage.get(usage_type, 0)
    remaining = max(0, limit - used)

    return {
        "allowed": used < limit,
        "plan": plan,
        "used": used,
        "limit": limit,
        "remaining": remaining,
        "usage_type": usage_type,
    }


def consume_quota(uid: str, usage_type: str) -> dict:
    result = check_quota(uid, usage_type)
    if not result["allowed"]:
        plan = result["plan"]
        raise HTTPException(
            status_code=429,
            detail={
                "error": "quota_exceeded",
                "message": f"Limite atteinte pour '{usage_type}' (plan {plan}).",
                "plan": plan,
                "used": result["used"],
                "limit": result["limit"],
                "remaining": 0,
                "usage_type": usage_type,
            }
        )
    increment_usage(uid, usage_type)
    return check_quota(uid, usage_type)


# ============================================================
# STRIPE — Création du paiement (NOUVEAU)
# ============================================================
async def create_stripe_payment(uid: str, email: str) -> dict:
    """
    Crée une session Stripe Checkout pour le plan Premium.
    """
    try:
        # Configuration du prix en Euro (ex: 9.90 EUR)
        # unit_amount est en centimes (990 = 9.90€)
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'eur',
                    'product_data': {
                        'name': 'PropIQ Premium — Plan Mensuel',
                        'description': 'Accès illimité aux analyses juridiques portugaises',
                    },
                    'unit_amount': 990,
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f"{STRIPE_SUCCESS_URL}?session_id={{CHECKOUT_SESSION_ID}}&uid={uid}",
            cancel_url=STRIPE_CANCEL_URL,
            customer_email=email,
            client_reference_id=uid,
        )

        logger.info(f"[Stripe] ✅ Session créée — uid={uid} | session_id={session.id}")
        return {
            "payment_url": session.url,
            "payment_ref": session.id,
        }
    except Exception as e:
        logger.error(f"[Stripe] ❌ Erreur creation session : {e}")
        raise HTTPException(status_code=500, detail=f"Erreur Stripe : {str(e)}")


async def verify_stripe_payment(session_id: str) -> dict:
    """
    Vérifie le statut d'une session Stripe.
    """
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        return {
            "status": "completed" if session.payment_status == "paid" else "pending",
            "amount": session.amount_total,
            "currency": session.currency,
        }
    except Exception as e:
        logger.error(f"[Stripe] ❌ Erreur vérification : {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# KONNECT — Fonctions conservées pour compatibilité
# ============================================================
async def create_konnect_payment(uid: str, email: str) -> dict:
    plan = PLANS["premium"]
    payload = {
        "receiverWalletId": KONNECT_WALLET_ID,
        "token": plan.get("currency", "TND"),
        "amount": plan["price"],
        "type": "immediate",
        "description": f"PropIQ Premium — {email}",
        "orderId": uid,
        "webhook": KONNECT_WEBHOOK_URL,
        "successUrl": f"{KONNECT_SUCCESS_URL}?uid={uid}",
        "failUrl": f"{KONNECT_FAIL_URL}?uid={uid}",
    }
    headers = {"x-api-key": KONNECT_API_KEY, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(f"{KONNECT_API_BASE}/payments/init-payment", json=payload, headers=headers)
    data = resp.json()
    return {"payment_url": data.get("payUrl"), "payment_ref": data.get("paymentRef")}


async def verify_konnect_payment(payment_ref: str) -> dict:
    headers = {"x-api-key": KONNECT_API_KEY}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{KONNECT_API_BASE}/payments/{payment_ref}", headers=headers)
    data = resp.json()
    payment = data.get("payment", {})
    return {
        "status": payment.get(
            "status", "unknown"), "amount": payment.get(
            "amount", 0), "currency": payment.get(
                "token", "TND")}


# ============================================================
# FACTORY — Switcher de provider
# ============================================================
async def create_payment(uid: str, email: str) -> dict:
    if PAYMENT_PROVIDER == "stripe":
        return await create_stripe_payment(uid, email)
    elif PAYMENT_PROVIDER == "konnect":
        return await create_konnect_payment(uid, email)
    else:
        raise HTTPException(status_code=500, detail=f"Provider inconnu : {PAYMENT_PROVIDER}")


async def verify_payment(payment_ref: str) -> dict:
    """
    ✅ FIX : Route le payment_ref vers le bon provider.
    Stripe session IDs commencent par 'cs_' (checkout session).
    Konnect payment refs ont un format différent.
    """
    # Détection automatique par préfixe du payment_ref
    if payment_ref.startswith("cs_") or PAYMENT_PROVIDER == "stripe":
        logger.info(f"[verify_payment] ✅ Stripe détecté — ref={payment_ref}")
        return await verify_stripe_payment(payment_ref)
    elif PAYMENT_PROVIDER == "konnect":
        logger.info(f"[verify_payment] ✅ Konnect détecté — ref={payment_ref}")
        return await verify_konnect_payment(payment_ref)
    else:
        raise HTTPException(status_code=500, detail=f"Provider inconnu : {PAYMENT_PROVIDER}")
