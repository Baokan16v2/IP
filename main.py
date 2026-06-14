import streamlit as st
import fitz  # PyMuPDF
import re
from PIL import Image
import io
import os

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
        # Extragem blocurile și le sortăm strict de sus în jos (axa Y)
        blocks = page.get_text("dict")["blocks"]
        blocks.sort(key=lambda b: b["bbox"][1])
        
        for b in blocks:
            # 1. TRATARE IMAGINI
            if b['type'] == 1:
                # Dacă dăm de o poză, o punem fix la întrebarea curentă
                if current_q is not None:
                    current_q["images"].append(b["image"])
                    
            # 2. TRATARE TEXT
            elif b['type'] == 0:
                text = ""
                for l in b["lines"]:
                    for s in l["spans"]:
                        text += s["text"] + " "
                
                # Curățăm spațiile și enter-urile inutile
                text = text.replace('\n', ' ').strip()

                if not text:
                    continue
                
                # Ignorăm numerele de pagină (ex: rânduri care conțin doar 1-3 cifre)
                if text.isdigit() and len(text) <= 3:
                    continue

                # DETECȚIE ÎNTREBARE NOUĂ: Caută format de tip "1. " sau "42."
                if re.match(r'^\d{1,3}\.', text):
                    if current_q:
                        questions.append(current_q)
                    current_q = {
                        "question": text, 
                        "options": [], 
                        "correct_idx": None, 
                        "images": []
                    }
                
                # DETECȚIE VARIANTĂ DE RĂSPUNS: Restricție severă (doar a,b,c,d,e,f urmate de paranteză)
                elif re.match(r'^[a-fA-F]\)', text.lower()) and current_q is not None:
                    is_correct = '*' in text
                    clean_text = text.replace('*', '').strip()
                    current_q["options"].append(clean_text)
                    
                    if is_correct:
                        current_q["correct_idx"] = len(current_q["options"]) - 1
                        
                # TEXT CONTINUARE: Dacă nu e nici întrebare nouă, nici variantă (a-f), e text de continuare
                elif current_q is not None:
                    if len(current_q["options"]) == 0:
                        # Dacă nu avem încă variante, lipim textul la întrebare (ex: o cerință lungă)
                        current_q["question"] += "\n" + text
                    else:
                        # Dacă avem deja variante, lipim textul la ultima variantă adăugată
                        current_q["options"][-1] += " " + text

    # Nu uităm să salvăm ultima întrebare găsită la finalul documentului
    if current_q:
        questions.append(current_q)

    return questions

# --- ÎNCĂRCARE DATE ---
DEFAULT_PDF = "Grile.pdf"
questions = []

if os.path.exists(DEFAULT_PDF):
    questions = parse_pdf(DEFAULT_PDF)
else:
    st.info("💡 Sfat: Pune fișierul 'Grile.pdf' în rădăcina proiectului pe Git.")
    uploaded_file = st.file_uploader("Sau încarcă manual fișierul PDF aici:", type="pdf")
    if uploaded_file is not None:
        questions = parse_pdf(uploaded_file.read())

# --- LOGICA APLICAȚIEI (INTERFAȚA) ---
if questions:
    st.title("🎯 Simulator Grile")
    
    if "user_answers" not in st.session_state:
        st.session_state.user_answers = {}
    if "current_index" not in st.session_state:
        st.session_state.current_index = 0

    st.sidebar.header("🧩 Navigare rapidă")
    q_titles = [f"Întrebarea {i+1}" for i in range(len(questions))]
    selected_q_idx = st.sidebar.selectbox("Mergi la:", q_titles, index=st.session_state.current_index)
    st.session_state.current_index = q_titles.index(selected_q_idx)
    
    answered_count = len(st.session_state.user_answers)
    st.sidebar.divider()
    st.sidebar.metric("Grile rezolvate", f"{answered_count} / {len(questions)}")

    idx = st.session_state.current_index
    q = questions[idx]

    st.subheader(f"Întrebarea {idx + 1} din {len(questions)}")
    st.markdown(f"**{q['question']}**")

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
