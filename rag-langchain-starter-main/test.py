# Thay vì: all-MiniLM-L12-v2
# Dùng một trong các model sau:

from sentence_transformers import SentenceTransformer
from langchain_community.embeddings import HuggingFaceEmbeddings
from sklearn.metrics.pairwise import cosine_similarity

# Option A: Tốt nhất cho tiếng Việt (khuyên dùng)
# model = SentenceTransformer('BAAI/bge-m3')

# Option B: Nếu GPU yếu, dùng paraphrase-multilingual (tốt hơn MiniLM rất nhiều)
# model = HuggingFaceEmbeddings('paraphrase-multilingual-mpnet-base-v2', cache_folder="./hugging_face/cache")
model = SentenceTransformer(model_name_or_path='paraphrase-multilingual-mpnet-base-v2', cache_folder="./hugging_face/cache")
# Option C: Chuyên biệt tiếng Việt
# model = SentenceTransformer('bkai-foundation-models/vietnamese-bi-encoder')

# Với all-MiniLM-L12-v2, chạy đoạn này sẽ thấy similarity thấp
emb1 = model.encode("cải mèo xào thịt")
emb2 = model.encode("cách làm cải mèo")
emb3 = model.encode("canh rau bóng bì")  # Món khác

print(f"Giống món cải mèo: {cosine_similarity([emb1], [emb2])[0][0]}")
print(f"Khác món: {cosine_similarity([emb1], [emb3])[0][0]}")
# Nếu 2 số gần nhau -> model không phân biệt được