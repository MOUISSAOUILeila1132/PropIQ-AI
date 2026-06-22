"""
PropIQ — Ingest Data to Pinecone (VERSION CORRIGÉE)
"""

import os
import re
import torch
from langchain_community.document_loaders import PyPDFLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_core.documents import Document
from pinecone import Pinecone, ServerlessSpec

from config import PINECONE_API_KEY, PINECONE_INDEX_NAME


def smart_split_legal_text(pages, category):
    full_text = "\n".join([p.page_content for p in pages])

    # Regex pour capturer les articles
    article_pattern = re.compile(
        r'(Artigo\s+\d+[^\n]*)\n(.*?)\n(.*?)(?=\nArtigo\s+\d+|$)',
        re.DOTALL)
    matches = article_pattern.findall(full_text)

    documents = []

    if matches:
        for match in matches:
            article_num = match[0].strip()[:100]  # Limite à 100 caractères
            topic = match[1].strip()[:200]        # Limite à 200 caractères
            content = match[2].strip()

            # PROTECTION TAILLE : Pinecone limite à 40KB de métadonnées.
            # On tronque le contenu à 25 000 caractères (~25KB) pour être sûr.
            if len(content) > 25000:
                content = content[:25000] + "... (truncated due to size)"

            doc = Document(
                page_content=content,
                metadata={
                    "article": article_num,
                    "topic": topic,
                    "category": category
                }
            )
            documents.append(doc)
    else:
        # FALLBACK : Si le regex ne trouve rien, on découpe par blocs de 2000 caractères
        print(
            f"⚠️ Structure 'Artigo' non détectée pour {category}, utilisation du découpage par blocs.")
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=200)
        chunks = splitter.split_text(full_text)
        for i, chunk in enumerate(chunks):
            documents.append(Document(
                page_content=chunk,
                metadata={
                    "article": f"Section {i+1}",
                    "topic": "General Content",
                    "category": category
                }
            ))

    return documents


def ingest_to_pinecone():
    root_dir = "Data"
    pc = Pinecone(api_key=PINECONE_API_KEY)

    # Création de l'index si inexistant
    if PINECONE_INDEX_NAME not in [idx.name for idx in pc.list_indexes()]:
        print(f"Creating Pinecone Index: {PINECONE_INDEX_NAME}...")
        pc.create_index(
            name=PINECONE_INDEX_NAME,
            dimension=768,
            metric='cosine',
            spec=ServerlessSpec(cloud='aws', region='us-east-1')
        )

    device = "cuda" if torch.cuda.is_available() else "cpu"
    embeddings = HuggingFaceEmbeddings(
        model_name="intfloat/multilingual-e5-base",
        model_kwargs={'device': device},
        encode_kwargs={'normalize_embeddings': True}
    )

    for subdir, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith(".pdf"):
                file_path = os.path.join(subdir, file)
                category = file.replace(".pdf", "").replace(" ", "_").replace(".", "_")

                print(f"\n--- Ingesting to Pinecone: {file} ---")
                try:
                    loader = PyPDFLoader(file_path)
                    pages = loader.load()
                    chunks = smart_split_legal_text(pages, category)

                    if not chunks:
                        continue

                    # Ajout du préfixe passage: pour E5
                    for doc in chunks:
                        doc.page_content = f"passage: {doc.page_content}"

                    # Upload vers Pinecone
                    # Note: On envoie par petits lots pour éviter les erreurs HTTP
                    batch_size = 50
                    for i in range(0, len(chunks), batch_size):
                        batch = chunks[i: i + batch_size]
                        PineconeVectorStore.from_documents(
                            documents=batch,
                            embedding=embeddings,
                            index_name=PINECONE_INDEX_NAME,
                            pinecone_api_key=PINECONE_API_KEY
                        )
                        print(
                            f"  Uploaded batch {i//batch_size + 1}/{(len(chunks)-1)//batch_size + 1}")

                    print(f"✅ Terminé : {len(chunks)} articles pour {file}")

                except Exception as e:
                    print(f"❌ Erreur critique avec {file}: {e}")


if __name__ == "__main__":
    ingest_to_pinecone()
