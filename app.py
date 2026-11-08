"""Render the Bock'n Bros account screens."""

import streamlit as st

import db
import logic


db.init_db()
st.title("Bock'n Bros")

if "user" in st.session_state:
    user = st.session_state.user
    st.header(f"Welcome, {user['username']}!")
    st.write(f"Role: {user['role'].title()}")
    if st.button("Log out"):
        del st.session_state["user"]
        st.rerun()
else:
    login_tab, signup_tab = st.tabs(["Log in", "Sign up"])
    with login_tab:
        with st.form("login_form"):
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Log in")
        if submitted:
            result = logic.login_user(db, username, password)
            if result.success:
                st.session_state.user = result.user
                st.rerun()
            st.error(result.message)
    with signup_tab:
        with st.form("signup_form"):
            username = st.text_input("Username", key="signup_username")
            password = st.text_input("Password", type="password", key="signup_password")
            password_repeat = st.text_input("Repeat password", type="password", key="signup_repeat")
            role_label = st.radio("Account type", ["Customer", "Business"])
            age_confirmed = st.checkbox("I confirm I am 18 or older")
            submitted = st.form_submit_button("Sign up")
        if submitted:
            result = logic.register_user(
                db, username, password, password_repeat, role_label.lower(), age_confirmed
            )
            if result.success:
                st.success(result.message)
            else:
                st.error(result.message)
