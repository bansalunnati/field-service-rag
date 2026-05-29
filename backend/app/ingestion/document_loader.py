from langchain_community.document_loaders import PyPDFLoader
import os

def load_documents(data_path="data/policies"):

    documents = []

    files = os.listdir(data_path)

    print(f"\nFound {len(files)} files\n")

    for file in files:

        if file.endswith(".pdf"):

            print(f"\nStarting: {file}")

            file_path = os.path.join(data_path, file)

            loader = PyPDFLoader(file_path)

            docs = loader.load()

            print(f"Loaded {len(docs)} pages from {file}")

            documents.extend(docs)

    return documents