import streamlit as st
import fitz  # PyMuPDF
import re
from PIL import Image
import io
import os

st.set_page_config(page_title="Simulator Grile", layout="centered", page_icon="📝")

# --- FUNCȚIE PARSARE PDF (REPARATĂ) ---
@st.cache_data
def parse_pdf(pdf_source):
    if isinstance(pdf_source, bytes):
        doc = fitz.open(stream=pdf_source, filetype="pdf")
    else:
        doc = fitz.open(pdf_source)
        
    questions = []
    current_q = None
    page_images = {} # Colectăm imaginile separat pentru fiecare pagină

    for page_num, page in enumerate(doc):
        blocks = page.get_text("dict")["blocks"]
        
        # 1. Separăm textul de imagini și îl sortăm de sus în jos după coordonata Y (bbox[1])
        text_blocks = [b for b in blocks if b['type'] == 0]
        text_blocks.sort(key=lambda b: b["bbox"][1])
        
        image_blocks = [b for b in blocks if b['type'] == 1]
        if image_blocks:
            page_images[page_num] = [b["image"] for b in image_blocks]

        # 2. Parsăm textul curățat și ordonat
        for b in text_blocks:
            text = ""
            for l in b["lines"]:
                for s in l["spans"]:
                    text += s["text"] + " "
            text = text.strip()

            if not text:
                continue
            
            # Ignorăm headere/footere izolate (ex: numere de pagină)
            if text.isdigit() and len(text) <= 3:
                continue

            # Întrebare nouă (suportă și spații înainte: " 1.", "23)")
            if re.match(r'^\s*\d+[\.\)]', text):
                if current_q:
                    questions.append(current_q)
                current_q = {
                    "question": text, 
                    "options": [], 
                    "correct_idx": None, 
                    "images": [],
                    "page": page_num # Reținem unde a apărut întrebarea
                }
            
            # Variantă de răspuns ("a)", " B. ")
            elif re.match(r'^\s*[a-eA-E][\)\.]', text) and current_q is not None:
                is_correct = '*' in text
                clean_text = text.replace('*', '').strip()
                current_q["options"].append(clean_text)
                
                if is_correct:
                    current_q["correct_idx"] = len(current_q["options"]) - 1
                    
            # Text adițional - îl alipim la locul potrivit
            elif current_q is not None:
                if len(current_q["options"]) == 0:
                    current_q["question"] += "\n" + text
                else:
                    current_q["options"][-1] += " " + text

    # Salvăm ultima întrebare din buclă
    if current_q:
        questions.append(current_q)

    # 3. ASIGNARE INTELIGENTĂ A IMAGINILOR
    # Căutăm cuvinte care ne "trădează" că întrebarea are nevoie de o poză
    keywords = ['figur', 'diagram', 'mai jos', 'codul', 'grafic']
    
    for p_num, images in page_images.items():
        # Extragem întrebările de pe pagina curentă (sau adiacente pentru overlap)
        candidate_qs = [q for q in questions if q["page"] in (p_num, p_num - 1, p_num + 1)]
        
        for img_bytes in images:
            assigned = False
            # Strategia A: Match pe cuvinte cheie
            for q in candidate_qs:
                if any(kw in q["question"].lower() for kw in keywords):
                    q["images"].append(img_bytes)
                    assigned = True
                    break
            
            # Strategia B: Fallback (dacă nu găsim cuvinte cheie, o dăm primei întrebări de pe pagină)
            if not assigned:
                qs_on_page = [q for q in questions if q["page"] == p_num]
                if qs_on_page:
                    qs_on_page[0]["images"].append(img_bytes)

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

    if q["images"]:
        for img_bytes in q["images"]:
            try:
                image = Image.open(io.BytesIO(img_bytes))
                st.image(image, use_container_width=True)
            except Exception:
                pass # Ignorăm subtil erorile de decodare a imaginii

    if q["options"]:
        saved_ans = st.session_state.user_answers.get(idx, None)
        default_radio_idx = q["options"].index(saved_ans) if saved_ans in q["options"] else None

        user_choice = st.radio(
            "Alege varianta:",
            q["options"],
            index=default_radio_idx,
            key=f"radio_{idx}"
        )
        
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

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("⬅️ Înapoi", disabled=(idx == 0)):
            st.session_state.current_index -= 1
            st.rerun()
    with col2:
        if st.button("Înainte ➡️", disabled=(idx == len(questions) - 1)):
            st.session_state.current_index += 1
            st.rerun()
