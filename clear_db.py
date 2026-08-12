import firebase_admin
from firebase_admin import credentials, firestore

# تهيئة الاتصال بـ Firebase بمشروع turki-2030
if not firebase_admin._apps:
  cred = credentials.Certificate("serviceAccountKey.json")
  firebase_admin.initialize_app(cred, {"projectId": "turki-2030"})

db = firestore.client()


def delete_collection(collection_ref, batch_size):
  docs = list(collection_ref.limit(batch_size).stream())
  deleted = 0

  if not docs:
    return 0

  batch = db.batch()
  for doc in docs:
    batch.delete(doc.reference)
    deleted += 1

  batch.commit()
  return deleted


collection_path = "transactions"
collection_ref = db.collection(collection_path)

print(f"🗑️ جاري مسح وتنظيف مجموعة '{collection_path}' من Firebase...")

total_deleted = 0
while True:
  deleted = delete_collection(collection_ref, batch_size=100)
  total_deleted += deleted
  if deleted == 0:
    break
  print(f"تم حذف {total_deleted} مستند حتى الآن...")

print(
    f"\n✅ تمت عملية التنظيف بنجاح! تم حذف جميع الحركات المالية ({total_deleted}"
    " مستند)."
)