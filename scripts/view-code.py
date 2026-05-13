from fastapi import FastAPI
import evariste

app = FastAPI()
evariste.attach(app)  # That's it!


@app.get("/users/{user_id}")
def get_user(user_id: str):
    return load(user_id)
