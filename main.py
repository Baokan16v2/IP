import streamlit as st
import fitz  # PyMuPDF
import re
from PIL import Image
import io
import os
import random

st.set_page_config(page_title="Simulator Grile", layout="centered", page_icon="📝")

# --- FUNCȚIE PARSARE PDF (STRICTĂ) ---
@st.cache_data
def parse_pdf(pdf_source):
    if isinstance(pdf_source, bytes):
        doc = fitz.open(stream=pdf_source, filetype="pdf")
    else:
        doc = fitz.open(pdf_source)
        
    questions = []
    current_q = None

    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        blocks.sort(key=lambda b: b["bbox"][1])
        
        for b in blocks:
            if b['type'] == 1:
                if current_q is not None:
                    current_q["images"].append(b["image"])
                    
            elif b['type'] == 0:
                text = ""
                for l in b["lines"]:
                    for s in l["spans"]:
                        text += s["text"] + " "
                
                text = text.replace('\n', ' ').strip()

                if not text:
                    continue
                
                if text.isdigit() and len(text) <= 3:
                    continue

                if re.match(r'^\d{1,3}\.', text):
                    if current_q:
                        questions.append(current_q)
                    current_q = {
                        "question": text, 
                        "options": [], 
                        "correct_idx": None, 
                        "images": []
                    }
                
                elif re.match(r'^[a-fA-F]\)', text.lower()) and current_q is not None:
                    is_correct = '*' in text
                    clean_text = text.replace('*', '').strip()
                    current_q["options"].append(clean_text)
                    
                    if is_correct:
                        current_q["correct_idx"] = len(current_q["options"]) - 1
                        
                elif current_q is not None:
                    if len(current_q["options"]) == 0:
                        current_q["question"] += "\n" + text
                    else:
                        current_q["options"][-1] += " " + text

    if current_q:
        questions.append(current_q)

    return questions

# --- ÎNCĂRCARE DATE ---
DEFAULT_PDF = "Grile.pdf"
raw_questions = []

if os.path.exists(DEFAULT_PDF):
    raw_questions = parse_pdf(DEFAULT_PDF)
else:
    st.info("💡 Sfat: Pune fișierul 'Grile.pdf' în rădăcina proiectului pe Git.")
    uploaded_file = st.file_uploader("Sau încarcă manual fișierul PDF aici:", type="pdf")
    if uploaded_file is not None:
        raw_questions = parse_pdf(uploaded_file.read())

# --- LOGICA APLICAȚIEI (INTERFAȚA) ---
if raw_questions:
    st.title("🎯 Simulator Grile")
    
    # Inițializăm starea sesiunii cu lista DEJA amestecată
    if "quiz_questions" not in st.session_state:
        shuffled_initial = raw_questions.copy()
        random.shuffle(shuffled_initial)
        st.session_state.quiz_questions = shuffled_initial
        
    if "user_answers" not in st.session_state:
        st.session_state.user_answers = {}
    if "current_index" not in st.session_state:
        st.session_state.current_index = 0

    questions = st.session_state.quiz_questions

    # Setări de randomizare în sidebar
    st.sidebar.header("🔀 Opțiuni Test")
    if st.sidebar.button("🔄 Începe un test nou"):
        # La un test nou, amestecăm iar și resetăm contoarele
        shuffled = raw_questions.copy()
        random.shuffle(shuffled)
        st.session_state.quiz_questions = shuffled
        st.session_state.user_answers = {}
        st.session_state.current_index = 0
        st.rerun()

    st.sidebar.divider()

    # Navigare
    st.sidebar.header("🧩 Navigare rapidă")
    q_titles = [f"Întrebarea {i+1} din {len(questions)}" for i in range(len(questions))]
    
    safe_index = min(st.session_state.current_index, len(questions) - 1)
    
    selected_q_idx = st.sidebar.selectbox("Mergi la:", q_titles, index=safe_index)
    st.session_state.current_index = q_titles.index(selected_q_idx)
    
    answered_count = len(st.session_state.user_answers)
    st.sidebar.metric("Grile rezolvate", f"{answered_count} / {len(questions)}")

    # Afișarea întrebării curente
    idx = st.session_state.current_index
    q = questions[idx]

    st.subheader(f"Întrebarea {idx + 1} / {len(questions)}")
    
    # ELIMINĂM INDEXUL ORIGINAL (ex: "42. ") DIN TEXTUL ÎNTREBĂRII
    clean_question = re.sub(r'^\d{1,3}\.\s*', '', q['question'])
    st.markdown(f"**{clean_question}**")

    # Afișare poze
    if q["images"]:
        for img_bytes in q["images"]:
            try:
                image = Image.open(io.BytesIO(img_bytes))
                st.image(image, use_container_width=True)
            except Exception:
                pass 

    # Afișare opțiuni radio
    if q["options"]:
        saved_ans = st.session_state.user_answers.get(idx, None)
        default_radio_idx = q["options"].index(saved_ans) if saved_ans in q["options"] else None

        user_choice = st.radio(
            "Alege varianta:",
            q["options"],
            index=default_radio_idx,
            key=f"radio_{idx}"
        )
        
        # Feedback instantaneu
        if user_choice:
            st.session_state.user_answers[idx] = user_choice

            if q["correct_idx"] is not None:
                correct_text = q["options"][q["correct_idx"]]
                if user_choice == correct_text:
                    st.success(f"🎉 Corect! Răspunsul este: **{correct_text}**")
                else:
                    st.error(f"❌ Greșit! Răspunsul corect era: **{correct_text}**")
            else:
                st.warning("Răspunsul corect nu este marcat în PDF pentru această grilă.")

    st.divider()

    # Butoane navigare
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("⬅️ Înapoi", disabled=(idx == 0)):
            st.session_state.current_index -= 1
            st.rerun()
    with col2:
        if st.button("Înainte ➡️", disabled=(idx == len(questions) - 1)):
            st.session_state.current_index += 1
            st.rerun()
