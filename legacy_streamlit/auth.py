import streamlit as st

def check_password() -> bool:
    """Returns True only if the user has already authenticated this session."""
    if st.session_state.get("authenticated", False):
        return True

    try:
        app_password = st.secrets["APP_PASSWORD"]
    except (KeyError, Exception):
        return True

    st.markdown(
        "<h2 style='text-align:center; margin-top: 20vh;'>🍽️ Meal Planner</h2>"
        "<p style='text-align:center; color:#64748b;'>Enter the access password to continue.</p>",
        unsafe_allow_html=True,
    )
    _, col, _ = st.columns([1, 1, 1])
    with col:
        entered = st.text_input("Password", type="password", label_visibility="collapsed",
                                placeholder="Enter password…")
        if st.button("Unlock →", use_container_width=True):
            if entered == app_password:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    st.stop()
    return False
