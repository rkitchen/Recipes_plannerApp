from backend.config import get_settings
from backend.services.firestore import init_firebase, get_db
from firebase_admin import auth

def test():
    print("Init firebase...")
    init_firebase()
    db = get_db()
    
    user_id = "test_user_id_123"
    print(f"Checking user {user_id}...")
    doc_ref = db.collection("users").document(user_id)
    doc = doc_ref.get()
    
    print(f"Exists: {doc.exists}")
    
    print("Setting document...")
    doc_ref.set({
        "email": "test@test.com",
        "liked_recipes": [],
        "disliked_recipes": [],
        "preferences": {}
    })
    print("Success!")

if __name__ == "__main__":
    test()
