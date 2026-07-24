import chromadb

# 1. Persistent client — data saved to ./chroma_db folder on disk
client = chromadb.PersistentClient(path="chroma_db")

# 2. Create the collection (get it if it already exists — safe to re-run)
collection = client.get_or_create_collection("coverage_kb")

print("Collection:", collection.name)
print("Records in it:", collection.count())