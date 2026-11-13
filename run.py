"""Start with: python run.py  (then visit http://127.0.0.1:8000)"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("korden.api:app", host="127.0.0.1", port=8000, reload=False)
