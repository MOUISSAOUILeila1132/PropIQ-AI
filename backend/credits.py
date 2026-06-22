"""
PropIQ — Credits System
Gestion des crédits quotidiens par utilisateur et par IP (anonymes).

Limites :
  - Anonyme (IP)   : 5 requêtes / jour
  - Inscrit (email): 20 requêtes / jour
  - Admin          : illimité

Reset : automatique chaque jour à minuit UTC.
"""

import logging
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Date, Boolean, ForeignKey
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURATION DES LIMITES
# ============================================================
CREDITS_CONFIG = {
    "anonymous": 5,   # utilisateur non connecté (limité par IP)
    "registered": 20,   # utilisateur connecté (limité par user_id)
    "admin": -1,   # illimité (-1 = pas de limite)
}

WARNING_THRESHOLD = 0.20   # Avertir quand il reste ≤ 20% des crédits


# ============================================================
# MODÈLE SQLAlchemy — Table des crédits
# ============================================================
def get_credits_model(Base):
    """
    Retourne le modèle CreditsTable à attacher à la Base SQLAlchemy existante.
    Appeler dans app.py AVANT Base.metadata.create_all().
    """
    class CreditsTable(Base):
        __tablename__ = "credits"
        id = Column(Integer, primary_key=True, index=True)
        # user_id null → utilisateur anonyme identifié par ip_address
        user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
        ip_address = Column(String, nullable=True, index=True)
        used = Column(Integer, default=0)
        limit = Column(Integer, default=CREDITS_CONFIG["anonymous"])
        reset_date = Column(Date, default=date.today)
        is_admin = Column(Boolean, default=False)

    return CreditsTable


# ============================================================
# HELPERS INTERNES
# ============================================================
def _today() -> date:
    return datetime.utcnow().date()


def _get_or_create_row(db: Session, CreditsTable, user_id=None, ip_address=None):
    """
    Récupère ou crée la ligne de crédits pour cet utilisateur/IP.
    Remet à zéro si le jour a changé.
    """
    today = _today()

    # Chercher par user_id (priorité) ou par ip
    if user_id:
        row = db.query(CreditsTable).filter(CreditsTable.user_id == user_id).first()
    else:
        row = db.query(CreditsTable).filter(
            CreditsTable.ip_address == ip_address,
            CreditsTable.user_id.is_(None)
        ).first()

    # Créer la ligne si elle n'existe pas
    if not row:
        limit = CREDITS_CONFIG["registered"] if user_id else CREDITS_CONFIG["anonymous"]
        row = CreditsTable(
            user_id=user_id,
            ip_address=ip_address if not user_id else None,
            used=0,
            limit=limit,
            reset_date=today,
            is_admin=False,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        logger.info(
            f"[Credits] Nouvelle ligne créée — user_id={user_id} | ip={ip_address} | limit={limit}")
        return row

    # Remettre à zéro si nouveau jour
    if row.reset_date != today:
        logger.info(f"[Credits] Reset quotidien — user_id={user_id} | ip={ip_address}")
        row.used = 0
        row.reset_date = today
        # Mise à jour de la limite si l'utilisateur s'est inscrit entre temps
        if user_id and row.limit == CREDITS_CONFIG["anonymous"]:
            row.limit = CREDITS_CONFIG["registered"]
        db.commit()
        db.refresh(row)

    return row


# ============================================================
# API PUBLIQUE
# ============================================================

def get_credits_status(
    db: Session,
    CreditsTable,
    user_id: int = None,
    ip_address: str = None,
    user_plan: str = None,
) -> dict:
    """
    Retourne le statut des crédits sans les modifier.

    Retourne:
        {
            "allowed":        bool,
            "used":           int,
            "limit":          int,
            "remaining":      int,
            "is_admin":       bool,
            "warning":        bool,    ← True si ≤ 20% restants
            "reset_date":     str,     ← "2025-07-01"
            "user_type":      str,     ← "anonymous" | "registered" | "admin"
            "message":        str,
        }
    """
    row = _get_or_create_row(db, CreditsTable, user_id=user_id, ip_address=ip_address)

    if row.is_admin:
        return {
            "allowed": True,
            "used": row.used,
            "limit": -1,
            "remaining": -1,
            "is_admin": True,
            "warning": False,
            "reset_date": str(row.reset_date),
            "user_type": "admin",
            "message": "Admin — unlimited access.",
        }

    remaining = row.limit - row.used
    allowed = remaining > 0
    warning = allowed and (remaining / row.limit) <= WARNING_THRESHOLD
    user_type = "registered" if user_id else "anonymous"

    if not allowed:
        msg = (
            f"Daily limit reached ({row.limit} requests). "
            f"Your credits reset tomorrow at midnight UTC."
        )
    elif warning:
        msg = f"⚠️ Only {remaining} credit(s) left today."
    else:
        msg = f"{remaining} credit(s) remaining today."

    return {
        "allowed": allowed,
        "used": row.used,
        "limit": row.limit,
        "remaining": remaining,
        "is_admin": False,
        "warning": warning,
        "reset_date": str(row.reset_date),
        "user_type": user_type,
        "message": msg,
    }


def consume_credit(
    db: Session,
    CreditsTable,
    user_id: int = None,
    ip_address: str = None,
    user_plan: str = None,
) -> dict:
    """
    Tente de consommer 1 crédit.

    Retourne le même dict que get_credits_status() avec:
        "consumed": bool  ← True si le crédit a été débité
    """
    status = get_credits_status(db, CreditsTable, user_id=user_id, ip_address=ip_address)

    if not status["allowed"] and not status["is_admin"]:
        return {**status, "consumed": False}

    # Admin → pas de débit
    if status["is_admin"]:
        return {**status, "consumed": True}

    # Débiter
    row = _get_or_create_row(db, CreditsTable, user_id=user_id, ip_address=ip_address)
    row.used += 1
    db.commit()
    db.refresh(row)

    remaining = row.limit - row.used
    warning = (remaining / row.limit) <= WARNING_THRESHOLD if row.limit > 0 else False

    logger.info(
        f"[Credits] Consommé — user_id={user_id} | ip={ip_address} "
        f"| used={row.used}/{row.limit}"
    )

    return {
        "consumed": True,
        "allowed": remaining >= 0,
        "used": row.used,
        "limit": row.limit,
        "remaining": remaining,
        "is_admin": False,
        "warning": warning,
        "reset_date": str(row.reset_date),
        "user_type": "registered" if user_id else "anonymous",
        "message": f"{remaining} credit(s) remaining today." if remaining > 0
        else "Daily limit reached. Come back tomorrow!",
    }


def set_admin(db: Session, CreditsTable, user_id: int, is_admin: bool = True):
    """
    Passe un utilisateur en mode admin (accès illimité).
    """
    row = _get_or_create_row(db, CreditsTable, user_id=user_id)
    row.is_admin = is_admin
    row.limit = CREDITS_CONFIG["admin"] if is_admin else CREDITS_CONFIG["registered"]
    db.commit()
    logger.info(f"[Credits] Admin={'ON' if is_admin else 'OFF'} — user_id={user_id}")


def reset_credits(db: Session, CreditsTable, user_id: int = None, ip_address: str = None):
    """
    Force la remise à zéro immédiate (utile pour les tests ou support).
    """
    row = _get_or_create_row(db, CreditsTable, user_id=user_id, ip_address=ip_address)
    row.used = 0
    row.reset_date = _today()
    db.commit()
    logger.info(f"[Credits] Reset forcé — user_id={user_id} | ip={ip_address}")
