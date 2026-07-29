Semantic Search Project
This is a project I do in my internship at The Hindu
This is Phase 1 of the project "Semantic Search" which is further developed into "RAG" and then into "Knowledge Graphs"!!

At first as my design plan I would like to share the tech stack I have choosed for this project
Pdf Object storage: MinIO
Vector DB: Cloudfare (cloud)
Embedding model: Semmetric Retrieval - all-MiniLM-L6-v2
Chunking Strategy: Paragraph based chunking with Overlapping

I have created a repo in github first and cloned the repo here and working on it

I will document how I create this project and things I do learn in this project from scratch
    1. I learned how to create a .venv envroinment, how to activate/ deactivate it
    2. I created an structure for my project initially have modularity first
    3. I created - pyproject.toml file (Replacement for requirements.txt), 
                - .gitignore(Files that gets rejected while pushing into VCS), 
                - .env(To change config files without changing code while adapting to new enviroinments), - - src folder which contains all of my main code
    4. Let's begin coding

I have used the classsical pipeline for Semantic search
- Extraction: I have used pyMuPdf which extracts text from pdf along with metadata such as charstart, charend and bounding boxes of the chunk
- Chunking: I have used paragraph based chunking at the word limit of 300 and 10% overlap.
- Embedding: I have used all-MiniLM-L6-v2 which is a symmetric retrieval strategy which uses the same embedding model for both embedding the doc as well as query
- Storage: I have used MinIO for the object storage which stores all the pdfs uploaded. It runs through docker( which needed wsl Linux Envroinment- Ubuntu to run) We can see the UI of MinIO through 127.0.0.1:9001 for the storage of all the documents
- Vectorize: I have used cloudfare as the vector db which is a cloud and offers 2,00,000 vector indexes in free tier and we can also view the Vectors and indexes in cloudfare dashboard in Vectorize under AI. It stores all the vectors from the embeddings


At first for running the application inside venv

    1.For starting MinIO - start the app Docker Desktop, run the command docker compose up -d, check in UI on port 8000
    2. For vectorize run src/vectorize_setup.py only for first time
    3. Run "pip install -e" to install dependencies from pyproject.toml file


