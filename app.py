import streamlit as st
import sqlite3
import hashlib
from datetime import datetime, timedelta
import jwt
import bcrypt
import os
import re
from email_validator import validate_email, EmailNotValidError

# Загружаем переменные из secrets.toml (для Streamlit Cloud)
# или из .env (для локальной разработки)
try:
    from dotenv import load_dotenv
    load_dotenv()
    USE_ENV = True
except:
    USE_ENV = False

def get_config(key, default=None):
    """Получает конфиг из secrets.toml или .env"""
    if hasattr(st, 'secrets') and key in st.secrets.get('env', {}):
        return st.secrets['env'][key]
    elif USE_ENV:
        return os.getenv(key, default)
    else:
        return default

DB_NAME = get_config("DB_NAME", "markettools.db")
SECRET_KEY = get_config("SECRET_KEY", "fallback-secret-key")
YANDEXGPT_API_KEY = get_config("YANDEXGPT_API_KEY")
YANDEXGPT_FOLDER_ID = get_config("YANDEXGPT_FOLDER_ID")
YOOKASSA_SHOP_ID = get_config("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = get_config("YOOKASSA_SECRET_KEY")

# Rate limiting - отслеживание попыток входа
if "login_attempts" not in st.session_state:
    st.session_state.login_attempts = {}

@st.cache_resource
def get_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            balance REAL DEFAULT 100.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tool_name TEXT NOT NULL,
            cost REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    conn.commit()

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password, hashed):
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except:
        return False

def check_password_legacy(password, hashed):
    return hashlib.sha256(password.encode()).hexdigest() == hashed

def is_bcrypt_hash(hashed):
    return hashed.startswith('$2b$') or hashed.startswith('$2a$')

def migrate_password(user_id, password):
    new_hash = hash_password(password)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (new_hash, user_id)
    )
    conn.commit()

def validate_email_address(email):
    try:
        valid = validate_email(email)
        return True, valid.email
    except EmailNotValidError as e:
        return False, str(e)

def check_rate_limit(ip_address, max_attempts=5, window_minutes=15):
    now = datetime.now()
    if ip_address not in st.session_state.login_attempts:
        st.session_state.login_attempts[ip_address] = []
    
    st.session_state.login_attempts[ip_address] = [
        attempt for attempt in st.session_state.login_attempts[ip_address]
        if (now - attempt).total_seconds() < window_minutes * 60
    ]
    
    if len(st.session_state.login_attempts[ip_address]) >= max_attempts:
        return False, f"Too many attempts. Try again in {window_minutes} minutes."
    return True, ""

def record_login_attempt(ip_address):
    if ip_address not in st.session_state.login_attempts:
        st.session_state.login_attempts[ip_address] = []
    st.session_state.login_attempts[ip_address].append(datetime.now())

def create_token(user_id, email):
    payload = {
        'user_id': user_id,
        'email': email,
        'exp': datetime.utcnow() + timedelta(days=7),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

def decode_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def register_user(email, password):
    is_valid, result = validate_email_address(email)
    if not is_valid:
        return False, f"Invalid email: {result}"
    
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'\d', password):
        return False, "Password must contain at least one digit"
    
    conn = get_connection()
    cursor = conn.cursor()
    try:
        password_hash = hash_password(password)
        cursor.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (result, password_hash)
        )
        conn.commit()
        return True, "Registration successful! 100 rubles bonus added."
    except sqlite3.IntegrityError:
        return False, "User with this email already exists."

def login_user(email, password, ip_address=None):
    if ip_address:
        allowed, message = check_rate_limit(ip_address)
        if not allowed:
            return False, message
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    
    if user:
        user_dict = dict(user)
        password_hash = user_dict['password_hash']
        
        if is_bcrypt_hash(password_hash) and check_password(password, password_hash):
            if ip_address and ip_address in st.session_state.login_attempts:
                del st.session_state.login_attempts[ip_address]
            return True, user_dict
        elif not is_bcrypt_hash(password_hash) and check_password_legacy(password, password_hash):
            migrate_password(user_dict['id'], password)
            if ip_address and ip_address in st.session_state.login_attempts:
                del st.session_state.login_attempts[ip_address]
            return True, user_dict
        else:
            if ip_address:
                record_login_attempt(ip_address)
            return False, "Invalid email or password."
    else:
        if ip_address:
            record_login_attempt(ip_address)
        return False, "Invalid email or password."

def get_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    return dict(user) if user else None

def update_balance(user_id, amount):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET balance = balance + ? WHERE id = ?",
        (amount, user_id)
    )
    conn.commit()

def add_transaction(user_id, tool_name, cost):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO transactions (user_id, tool_name, cost) VALUES (?, ?, ?)",
        (user_id, tool_name, cost)
    )
    conn.commit()

def get_user_transactions(user_id, limit=10):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    )
    transactions = [dict(row) for row in cursor.fetchall()]
    return transactions

# Инициализация БД
init_db()

st.set_page_config(page_title="MarketTools", page_icon="🛠️", layout="wide")

# Инициализация session state
if "user" not in st.session_state:
    st.session_state.user = None
if "seo_result" not in st.session_state:
    st.session_state.seo_result = None
if "card_result" not in st.session_state:
    st.session_state.card_result = None
if "card_data" not in st.session_state:
    st.session_state.card_data = None
if "reviews_result" not in st.session_state:
    st.session_state.reviews_result = None
if "review_data" not in st.session_state:
    st.session_state.review_data = None
if "title_result" not in st.session_state:
    st.session_state.title_result = None
if "reply_result" not in st.session_state:
    st.session_state.reply_result = None

# Проверка токена при загрузке
if st.session_state.user is None:
    try:
        query_params = st.query_params
    except AttributeError:
        query_params = {}
    
    if query_params and "token" in query_params:
        token = query_params["token"]
        payload = decode_token(token)
        if payload:
            user = get_user(payload['user_id'])
            if user:
                st.session_state.user = user

def logout():
    st.session_state.user = None
    st.session_state.seo_result = None
    st.session_state.card_result = None
    st.session_state.card_data = None
    st.session_state.reviews_result = None
    st.session_state.review_data = None
    st.session_state.title_result = None
    st.session_state.reply_result = None
    try:
        st.query_params.clear()
    except:
        pass

# --- ЭКРАН АВТОРИЗАЦИИ / РЕГИСТРАЦИИ ---
if st.session_state.user is None:
    st.title("MarketTools")
    st.markdown("### Tools for marketplace sellers")
    st.markdown("---")
    
    st.markdown("### Login")
    login_email = st.text_input("Email", key="login_email")
    login_password = st.text_input("Password", type="password", key="login_password")
    
    try:
        ip_address = st.context.headers.get('X-Forwarded-For', '127.0.0.1')
    except:
        ip_address = '127.0.0.1'
    
    if st.button("Login", key="btn_login"):
        if login_email and login_password:
            success, result = login_user(login_email, login_password, ip_address)
            if success:
                st.session_state.user = result
                token = create_token(result['id'], result['email'])
                try:
                    st.query_params["token"] = token
                except:
                    pass
                st.success("Welcome!")
                st.rerun()
            else:
                st.error(result)
        else:
            st.warning("Fill all fields")
    
    st.markdown("---")
    st.markdown("### Register new account")
    st.info("You get 100 rubles bonus on registration!")
    
    reg_email = st.text_input("Email", key="reg_email")
    reg_password = st.text_input("Password", type="password", key="reg_password")
    reg_password2 = st.text_input("Repeat password", type="password", key="reg_password2")
    
    if st.button("Register", key="btn_register"):
        if reg_email and reg_password and reg_password2:
            if reg_password != reg_password2:
                st.error("Passwords do not match")
            else:
                success, message = register_user(reg_email, reg_password)
                if success:
                    st.success(message)
                    st.info("Now login using the form above")
                else:
                    st.error(message)
        else:
            st.warning("Fill all fields")
    
    with st.sidebar:
        st.markdown("### How it works:")
        st.markdown("1. Register")
        st.markdown("2. Get 100 rub bonus")
        st.markdown("3. Use tools")
        st.markdown("4. Pay only for use")

# --- ОСНОВНОЙ ЭКРАН ПРИЛОЖЕНИЯ ---
else:
    user = get_user(st.session_state.user["id"])
    st.session_state.user = user
    
    st.title("MarketTools")
    st.markdown("### Tools for marketplace sellers")
    st.markdown("---")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "SEO", 
        "Cards", 
        "Reviews", 
        "Titles", 
        "Replies"
    ])
    
    # TAB 1: SEO
    with tab1:
        st.subheader("SEO Descriptions")
        st.caption("Optimized for Ozon and WB")
        st.markdown("**Price: 99 rub.**")
        
        if st.session_state.seo_result:
            st.success(st.session_state.seo_result)
            if st.button("Clear", key="clear_seo"):
                st.session_state.seo_result = None
        else:
            product_info = st.text_area(
                "Product info:",
                placeholder="Example: orthopedic pillow, size 50x70",
                height=120,
                key="product_info"
            )
            
            if st.button("Generate", key="btn1"):
                if product_info:
                    if user["balance"] >= 99:
                        try:
                            with st.spinner("Generating..."):
                                from yandex_gpt import generate_description
                                description = generate_description(product_info)
                            
                            update_balance(user["id"], -99)
                            add_transaction(user["id"], "SEO description", 99)
                            st.session_state.seo_result = description
                            st.session_state.user = get_user(user["id"])
                            st.success("Done! -99 rub.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
                    else:
                        st.error("Not enough funds!")
                else:
                    st.warning("Enter product info")
    
    # TAB 2: CARDS
    with tab2:
        st.subheader("Product Cards")
        st.caption("With infographics for WB")
        st.markdown("**Price: 149 rub.**")
        
        if st.session_state.card_result:
            card_data = st.session_state.get('card_data', {})
            
            if isinstance(card_data, dict) and 'error' not in card_data:
                st.subheader(card_data.get('title', 'No title'))
                st.divider()
                
                st.markdown("**Description:**")
                st.write(card_data.get('description', ''))
                st.divider()
                
                st.markdown("**Advantages:**")
                for adv in card_data.get('advantages', [])[:7]:
                    st.write(f"- {adv}")
                st.divider()
                
                st.markdown("**Characteristics:**")
                for char in card_data.get('characteristics', []):
                    st.write(f"- {char}")
                st.divider()
                
                st.markdown("**Infographic texts:**")
                for i, block in enumerate(card_data.get('infographic', [])[:5], 1):
                    st.write(f"**Block {i}:** {block}")
                st.divider()
                
                keywords = card_data.get('keywords', [])
                if keywords:
                    st.markdown("**Keywords:**")
                    st.write(", ".join(keywords[:15]))
                
                st.divider()
                st.subheader("Download")
                
                col_dl1, col_dl2 = st.columns(2)
                
                with col_dl1:
                    try:
                        from export_card import create_txt_card
                        txt_content = create_txt_card(card_data)
                        safe_title = card_data.get('title', 'product')[:30].replace(' ', '_')
                        st.download_button(
                            label="TXT",
                            data=txt_content,
                            file_name=f"card_{safe_title}.txt",
                            mime="text/plain",
                            key="download_txt"
                        )
                    except Exception as e:
                        st.error(f"TXT error: {str(e)}")
                
                with col_dl2:
                    try:
                        from export_card import create_docx_card
                        docx_buffer = create_docx_card(card_data)
                        safe_title = card_data.get('title', 'product')[:30].replace(' ', '_')
                        st.download_button(
                            label="DOCX",
                            data=docx_buffer,
                            file_name=f"card_{safe_title}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key="download_docx"
                        )
                    except Exception as e:
                        st.error(f"DOCX error: {str(e)}")
            else:
                st.error(f"Error: {card_data.get('error', 'Unknown error')}")
            
            if st.button("Clear", key="clear_card"):
                st.session_state.card_result = None
                st.session_state.card_data = None
        else:
            product_name = st.text_input("Product name", placeholder="Orthopedic pillow", key="card_product_name")
            product_features = st.text_area("Characteristics", placeholder="Size: 50x70 cm\nMaterial: memory foam\nColor: white", height=150, key="card_features")
            target_audience = st.text_area("Target audience (optional)", placeholder="Who is this product for?", height=100, key="card_audience")
            marketplace = st.selectbox("Marketplace", ["Wildberries", "Ozon", "Universal"], key="card_marketplace")
            
            if st.button("Create Card", key="btn2", type="primary"):
                if product_name and product_features:
                    if user["balance"] >= 149:
                        try:
                            with st.spinner("Generating..."):
                                from product_card import generate_product_card
                                card_data = generate_product_card(product_name, product_features, target_audience)
                                
                                st.session_state.card_data = card_data
                                st.session_state.card_result = "generated"
                                update_balance(user["id"], -149)
                                add_transaction(user["id"], "Product card", 149)
                                st.session_state.user = get_user(user["id"])
                                st.success("Done! -149 rub.")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
                    else:
                        st.error("Not enough funds!")
                else:
                    st.warning("Fill in the fields")
    
    # TAB 3: REVIEWS
    with tab3:
        st.subheader("Reviews Analysis")
        st.caption("Competitor analysis")
        st.markdown("**Price: 199 rub.**")
        
        if st.session_state.reviews_result:
            review_data = st.session_state.get('review_data', {})
            if isinstance(review_data, dict) and review_data.get('success'):
                analysis = review_data.get('analysis', {})
                reviews = review_data.get('reviews', [])
                summary = analysis.get('summary', {})
                
                def filter_empty(lst):
                    return [item for item in lst if item and str(item).strip()]
                
                st.subheader("Statistics")
                col_stat1, col_stat2, col_stat3 = st.columns(3)
                with col_stat1: st.metric("Reviews", f"{summary.get('total_reviews', 0)}")
                with col_stat2: st.metric("Rating", f"{summary.get('average_rating', 0)}/5")
                with col_stat3: st.metric("Positive", f"{summary.get('positive_percentage', 0)}%")
                st.divider()
                
                st.subheader("Pros")
                pros = filter_empty(analysis.get('pros', [])[:5])
                for pro in pros: st.write(f"- {pro}") if pros else st.write("No data")
                st.divider()
                
                st.subheader("Cons")
                cons = filter_empty(analysis.get('cons', [])[:5])
                for con in cons: st.write(f"- {con}") if cons else st.write("No data")
                st.divider()
                
                st.subheader("Pain Points")
                pains = filter_empty(analysis.get('customer_pain_points', [])[:5])
                for pain in pains: st.write(f"- {pain}") if pains else st.write("No data")
                st.divider()
                
                st.subheader("Recommendations")
                recs = filter_empty(analysis.get('recommendations', [])[:5])
                for rec in recs: st.write(f"- {rec}") if recs else st.write("No data")
                st.divider()
                
                st.subheader("Target Audience")
                target = analysis.get('target_audience', 'Not defined')
                st.write(target) if target and str(target).strip() else st.write("Not defined")
                st.divider()
                
                st.subheader("Download Report")
                col_dl1, col_dl2 = st.columns(2)
                with col_dl1:
                    try:
                        from export_review_report import create_review_report_txt
                        st.download_button(label="TXT", data=create_review_report_txt(analysis, reviews), file_name="review_analysis.txt", mime="text/plain", key="download_review_txt")
                    except Exception as e: st.error(f"TXT error: {str(e)}")
                with col_dl2:
                    try:
                        from export_review_report import create_review_report_docx
                        st.download_button(label="DOCX", data=create_review_report_docx(analysis, reviews), file_name="review_analysis.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", key="download_review_docx")
                    except Exception as e: st.error(f"DOCX error: {str(e)}")
            else:
                st.error(f"Error: {review_data.get('error', 'Error') if isinstance(review_data, dict) else 'Error'}")
            
            if st.button("Clear", key="clear_reviews"):
                st.session_state.reviews_result = None
                st.session_state.review_data = None
        else:
            st.info("Paste reviews from website")
            reviews_text = st.text_area("Reviews:", placeholder="Great product!\n\nGood quality.", height=200, key="manual_reviews_text")
            product_name = st.text_input("Product name:", placeholder="Orthopedic pillow", key="review_product_name_manual")
            
            if st.button("Analyze", key="btn_manual", type="primary"):
                if reviews_text and user["balance"] >= 199:
                    try:
                        with st.spinner("Analyzing..."):
                            from reviews_parser import parse_manual_reviews, analyze_reviews_with_gpt
                            reviews_data = parse_manual_reviews(reviews_text)
                            if not reviews_data['reviews']:
                                st.warning("No reviews found")
                            else:
                                reviews = reviews_data['reviews']
                                st.info(f"Found {len(reviews)} reviews")
                                analysis_result = analyze_reviews_with_gpt(reviews, product_name if product_name else "product")
                                
                                if analysis_result.get('success'):
                                    st.session_state.review_data = {'success': True, 'analysis': analysis_result['analysis'], 'reviews': reviews, 'reviews_count': analysis_result['reviews_count']}
                                    st.session_state.reviews_result = "analyzed"
                                    update_balance(user["id"], -199)
                                    add_transaction(user["id"], "Reviews analysis", 199)
                                    st.session_state.user = get_user(user["id"])
                                    st.success("Done! -199 rub.")
                                    st.rerun()
                                else:
                                    st.error(f"Error: {analysis_result.get('error', 'Error')}")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
                elif not reviews_text:
                    st.warning("Enter reviews")
                else:
                    st.error("Not enough funds!")
    
    # TAB 4: TITLES
    with tab4:
        st.subheader("Title Generator")
        st.caption("SEO titles for WB/Ozon")
        st.markdown("**Price: 49 rub.**")
        
        if st.session_state.title_result:
            title_data = st.session_state.title_result
            if 'error' not in title_data:
                st.subheader("Generated Titles")
                st.markdown("**Best title:**")
                st.success(title_data.get('best_title', ''))
                st.divider()
                st.markdown("**All variants:**")
                for i, title in enumerate(title_data.get('titles', [])[:5], 1):
                    st.write(f"**{i}.** {title}")
                st.divider()
                st.markdown("**Keywords used:**")
                st.write(", ".join(title_data.get('keywords_used', [])))
                st.divider()
                st.subheader("Copy Best Title")
                st.code(title_data.get('best_title', ''), language='text')
            else:
                st.error(f"Error: {title_data.get('error', 'Unknown')}")
            
            if st.button("Clear", key="clear_title"):
                st.session_state.title_result = None
        else:
            product_name = st.text_input("Product name", placeholder="Orthopedic pillow", key="title_product_name")
            product_features = st.text_area("Characteristics", placeholder="Size: 50x70 cm\nMaterial: memory foam\nColor: white", height=120, key="title_features")
            marketplace = st.selectbox("Marketplace", ["Wildberries", "Ozon", "Universal"], key="title_marketplace")
            
            if st.button("Generate Titles", key="btn_title", type="primary"):
                if product_name and product_features:
                    if user["balance"] >= 49:
                        try:
                            with st.spinner("Generating..."):
                                from title_generator import generate_title
                                title_data = generate_title(product_name, product_features, marketplace)
                                st.session_state.title_result = title_data
                                update_balance(user["id"], -49)
                                add_transaction(user["id"], "Title generator", 49)
                                st.session_state.user = get_user(user["id"])
                                st.success("Done! -49 rub.")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
                    else:
                        st.error("Not enough funds!")
                else:
                    st.warning("Fill in the fields")
    
    # TAB 5: REPLIES
    with tab5:
        st.subheader("Review Replies")
        st.caption("Auto replies to customers")
        st.markdown("**Price: 29 rub. per reply**")
        
        if st.session_state.reply_result:
            reply_data = st.session_state.reply_result
            if 'error' not in reply_data:
                st.subheader("Generated Reply")
                st.markdown(f"**Tone:** {reply_data.get('tone', 'professional')}")
                st.divider()
                st.markdown("**Your reply:**")
                st.success(reply_data.get('reply', ''))
                st.divider()
                st.subheader("Copy Reply")
                st.code(reply_data.get('reply', ''), language='text')
            else:
                st.error(f"Error: {reply_data.get('error', 'Unknown')}")
            
            if st.button("Clear", key="clear_reply"):
                st.session_state.reply_result = None
        else:
            review_text = st.text_area("Customer review:", placeholder="Paste the customer review here...", height=150, key="reply_review_text")
            col_r1, col_r2 = st.columns(2)
            with col_r1:
                rating = st.slider("Customer rating:", 1, 5, 5, key="reply_rating")
            with col_r2:
                product_name = st.text_input("Product name:", placeholder="Orthopedic pillow", key="reply_product_name")
            
            if rating >= 4: st.info("Positive review - thank the customer")
            elif rating == 3: st.warning("Neutral review - be polite")
            else: st.error("Negative review - apologize and offer solution")
            
            if st.button("Generate Reply", key="btn_reply", type="primary"):
                if review_text:
                    if user["balance"] >= 29:
                        try:
                            with st.spinner("Generating..."):
                                from review_replier import generate_reply
                                reply_data = generate_reply(review_text, rating, product_name)
                                st.session_state.reply_result = reply_data
                                update_balance(user["id"], -29)
                                add_transaction(user["id"], "Review reply", 29)
                                st.session_state.user = get_user(user["id"])
                                st.success("Done! -29 rub.")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
                    else:
                        st.error("Not enough funds!")
                else:
                    st.warning("Enter review text")
    
    # SIDEBAR
    with st.sidebar:
        st.subheader("Account")
        st.markdown(f"**Email:** {user['email']}")
        st.markdown(f"**Balance:** {user['balance']:.2f} rub.")
        st.markdown("---")
        
        st.subheader("Add Balance")
        if st.button("💳 Пополнить баланс", key="add_balance"):
            st.switch_page("pages/6_Payment.py")
        
        st.markdown("---")
        st.subheader("History")
        transactions = get_user_transactions(user["id"], limit=10)
        if transactions:
            for t in transactions:
                cost = float(t["cost"])
                tool_name = str(t["tool_name"])
                created_at = str(t["created_at"])
                if cost < 0:
                    st.markdown(f"+ {-cost:.0f} rub ({tool_name})")
                else:
                    st.markdown(f"- {cost:.0f} rub ({tool_name})")
                st.caption(created_at)
        else:
            st.markdown("Empty")
        
        st.markdown("---")
        if st.button(" Logout", key="btn_logout"):
            logout()
            st.rerun()
        
        st.markdown("---")
        st.subheader("How it works:")
        st.markdown("1. Register")
        st.markdown("2. Get 100 rub bonus")
        st.markdown("3. Use tools")
        st.markdown("4. Pay for usage")