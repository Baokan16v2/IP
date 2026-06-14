import streamlit as st
import fitz  # PyMuPDF
import re
from PIL import Image
import io
import os

st.set_page_config(page_title="Simulator Grile", layout="centered", page_icon="📝")

# --- FUNCȚIE PARSARE PDF ---
@st.cache_data
def parse_pdf(pdf_source):
    """
    Parcurge PDF-ul (fie din bytes, fie cale de fișier), extrage textul și imaginile.
    """
    if isinstance(pdf_source, bytes):
        doc = fitz.open(stream=pdf_source, filetype="pdf")
    else:
        doc = fitz.open(pdf_source)
        
    questions = []
    current_q = None

    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        
        for b in blocks:
            # Bloc de TEXT
            if b['type'] == 0:
                text = ""
                for l in b["lines"]:
                    for s in l["spans"]:
                        text += s["text"] + " "
                text = text.strip()

                if not text:
                    continue

                # Întrebare nouă (Ex: "1. ", "23. ")
                if re.match(r'^\d+\.', text):
                    if current_q:
                        questions.append(current_q)
                    current_q = {
                        "question": text, 
                        "options": [], 
                        "correct_idx": None, 
                        "images": []
                    }
                
                # Variantă de răspuns (Ex: "a) ", "b) ")
                elif re.match(r'^[a-z]\)', text) and current_q is not None:
                    is_correct = '*' in text
                    clean_text = text.replace('*', '').strip()
                    current_q["options"].append(clean_text)
                    
                    if is_correct:
                        current_q["correct_idx"] = len(current_q["options"]) - 1
                        
                # Text adițional pentru întrebare
                elif current_q is not None and len(current_q["options"]) == 0:
                    current_q["question"] += "\n" + text
                    
                # Text adițional pentru ultima variantă
                elif current_q is not None and len(current_q["options"]) > 0:
                    current_q["options"][-1] += " " + text

            # Bloc de IMAGINE
            elif b['type'] == 1:
                if current_q is not None:
                    current_q["images"].append(b["image"])

    if current_q:
        questions.append(current_q)

    return questions

# --- ÎNCĂRCARE DATE AUTOMATĂ / MANUALĂ ---
DEFAULT_PDF = "Grile.pdf"
questions = []

if os.path.exists(DEFAULT_PDF):
    questions = parse_pdf(DEFAULT_PDF)
else:
    st.info("💡 Sfat: Pune fișierul 'Grile.pdf' în rădăcina repository-ului de Git pentru a se încărca automat.")
    uploaded_file = st.file_uploader("Sau încarcă manual fișierul PDF aici:", type="pdf")
    if uploaded_file is not None:
        questions = parse_pdf(uploaded_file.read())

# --- LOGICA APLICAȚIEI ---
if questions:
    st.title("🎯 Simulator Grile")
    
    # Inițializare stări în session_state pentru a nu pierde progresul la re-run
    if "user_answers" not in st.session_state:
        st.session_state.user_answers = {}
    if "current_index" not in st.session_state:
        st.session_state.current_index = 0

    # Sidebar pentru navigare
    st.sidebar.header("🧩 Navigare rapidă")
    q_titles = [f"Întrebarea {i+1}" for i in range(len(questions))]
    selected_q_idx = st.sidebar.selectbox("Mergi la:", q_titles, index=st.session_state.current_index)
    st.session_state.current_index = q_titles.index(selected_q_idx)
    
    # Statistici simple în sidebar
    answered_count = len(st.session_state.user_answers)
    st.sidebar.divider()
    st.sidebar.metric("Grile rezolvate", f"{answered_count} / {len(questions)}")

    # Întrebarea curentă
    idx = st.session_state.current_index
    q = questions[idx]

    st.subheader(f"Întrebarea {idx + 1} din {len(questions)}")
    st.markdown(f"**{q['question']}**")

    # Afișare imagini aferente întrebării
    if q["images"]:
        for img_bytes in q["images"]:
            try:
                image = Image.open(io.BytesIO(img_bytes))
                st.image(image, use_container_width=True)
            except Exception as e:
                st.error("Nu s-a putut reda o imagine din interiorul PDF-ului.")

    # Afișare opțiuni radio
    if q["options"]:
        # Identificăm indexul salvat anterior (dacă există) pentru a-l pre-selecta
        saved_ans = st.session_state.user_answers.get(idx, None)
        default_radio_idx = q["options"].index(saved_ans) if saved_ans in q["options"] else None

        user_choice = st.radio(
            "Alege varianta:",
            q["options"],
            index=default_radio_idx,
            key=f"radio_{idx}"
        )
        
        # Salvăm răspunsul și afișăm feedback instant
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

    # Butoane de navigare Înapoi / Înainte
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("⬅️ Înapoi", disabled=(idx == 0)):
            st.session_state.current_index -= 1
            st.rerun()
    with col2:
        if st.button("Înainte ➡️", disabled=(idx == len(questions) - 1)):
            st.session_state.current_index += 1
            st.rerun()