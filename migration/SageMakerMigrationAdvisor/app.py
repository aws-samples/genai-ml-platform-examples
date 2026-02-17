"""
Unified SageMaker Migration Advisor Application
Single frontend with mode selection and Cognito authentication
"""

import streamlit as st
import os
import json
import boto3
import hmac
import hashlib
import base64
from typing import Optional, Dict, Any
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure Streamlit page
st.set_page_config(
    page_title="SageMaker Migration Advisor",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    /* Main header styling */
    .main-header {
        font-size: 3rem;
        font-weight: 700;
        background: linear-gradient(135deg, #FF9933 0%, #FF6B35 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 1rem;
        padding: 1rem 0;
    }
    
    .subtitle {
        text-align: center;
        font-size: 1.2rem;
        color: #6c757d;
        margin-bottom: 3rem;
    }
    
    /* Login container */
    .login-container {
        max-width: 450px;
        margin: 0 auto;
        padding: 2.5rem;
        background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
        border-radius: 15px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
        border: 1px solid #e9ecef;
    }
    
    /* Mode selector cards */
    .mode-card {
        padding: 2rem;
        border-radius: 15px;
        background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
        margin: 1rem 0;
        border: 2px solid #e9ecef;
        transition: all 0.3s ease;
        box-shadow: 0 5px 15px rgba(0, 0, 0, 0.08);
        height: 100%;
    }
    
    .mode-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 15px 35px rgba(0, 0, 0, 0.15);
        border-color: #FF9933;
    }
    
    .mode-card-lite {
        border-left: 5px solid #17a2b8;
    }
    
    .mode-card-regular {
        border-left: 5px solid #FF6B35;
    }
    
    .mode-title {
        font-size: 1.5rem;
        font-weight: 600;
        margin-bottom: 1rem;
        color: #2c3e50;
    }
    
    .mode-description {
        font-size: 1rem;
        color: #6c757d;
        margin-bottom: 1.5rem;
        line-height: 1.6;
    }
    
    .feature-list {
        margin: 1.5rem 0;
    }
    
    .feature-item {
        padding: 0.5rem 0;
        font-size: 0.95rem;
        color: #495057;
    }
    
    .best-for {
        background-color: #f0f8ff;
        padding: 1rem;
        border-radius: 8px;
        margin-top: 1rem;
        border-left: 3px solid #17a2b8;
    }
    
    .best-for-title {
        font-weight: 600;
        color: #2c3e50;
        margin-bottom: 0.5rem;
    }
    
    /* Hero section */
    .hero-section {
        text-align: center;
        padding: 2rem 0;
        margin-bottom: 2rem;
    }
    
    .hero-icon {
        font-size: 4rem;
        margin-bottom: 1rem;
    }
    
    /* Stats cards */
    .stats-container {
        display: flex;
        justify-content: space-around;
        margin: 2rem 0;
        gap: 1rem;
    }
    
    .stat-card {
        flex: 1;
        padding: 1.5rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 10px;
        text-align: center;
        color: white;
        box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
    }
    
    .stat-number {
        font-size: 2rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    
    .stat-label {
        font-size: 0.9rem;
        opacity: 0.9;
    }
    
    /* Success and error boxes */
    .success-box {
        padding: 1rem;
        border-radius: 10px;
        background-color: #d4edda;
        border-left: 4px solid #28a745;
        color: #155724;
        margin: 1rem 0;
    }
    
    .error-box {
        padding: 1rem;
        border-radius: 10px;
        background-color: #f8d7da;
        border-left: 4px solid #dc3545;
        color: #721c24;
        margin: 1rem 0;
    }
    
    /* Sidebar styling */
    .sidebar-info {
        padding: 1rem;
        background-color: #f8f9fa;
        border-radius: 10px;
        margin: 1rem 0;
    }
    
    /* Button enhancements */
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
    }
</style>
""", unsafe_allow_html=True)


class CognitoAuth:
    """Handle Cognito authentication"""
    
    def __init__(self):
        self.client_id = os.getenv('COGNITO_CLIENT_ID')
        self.client_secret = os.getenv('COGNITO_CLIENT_SECRET')
        self.user_pool_id = os.getenv('COGNITO_USER_POOL_ID')
        self.region = os.getenv('AWS_REGION', 'us-east-1')
        
        if not all([self.client_id, self.user_pool_id]):
            st.warning("⚠️ Cognito not configured. Running in development mode.")
            self.enabled = False
        else:
            self.enabled = True
            self.cognito_client = boto3.client('cognito-idp', region_name=self.region)
    
    def get_secret_hash(self, username: str) -> str:
        """Generate secret hash for Cognito"""
        if not self.client_secret:
            return None
        
        message = bytes(username + self.client_id, 'utf-8')
        secret = bytes(self.client_secret, 'utf-8')
        dig = hmac.new(secret, message, hashlib.sha256).digest()
        return base64.b64encode(dig).decode()
    
    def authenticate(self, username: str, password: str) -> Dict[str, Any]:
        """Authenticate user with Cognito"""
        if not self.enabled:
            return {'success': True, 'user': username, 'dev_mode': True}
        
        try:
            auth_params = {
                'USERNAME': username,
                'PASSWORD': password
            }
            
            if self.client_secret:
                auth_params['SECRET_HASH'] = self.get_secret_hash(username)
            
            response = self.cognito_client.initiate_auth(
                ClientId=self.client_id,
                AuthFlow='USER_PASSWORD_AUTH',
                AuthParameters=auth_params
            )
            
            return {
                'success': True,
                'user': username,
                'tokens': response['AuthenticationResult'],
                'dev_mode': False
            }
        except self.cognito_client.exceptions.NotAuthorizedException:
            return {'success': False, 'error': 'Invalid username or password'}
        except self.cognito_client.exceptions.UserNotFoundException:
            return {'success': False, 'error': 'User not found'}
        except Exception as e:
            return {'success': False, 'error': f'Authentication error: {str(e)}'}
    
    def validate_token(self, access_token: str) -> bool:
        """Validate access token"""
        if not self.enabled:
            return True
        
        try:
            self.cognito_client.get_user(AccessToken=access_token)
            return True
        except:
            return False


class MigrationAdvisorApp:
    """Main application class"""
    
    def __init__(self):
        self.auth = CognitoAuth()
        self.initialize_session_state()
        self.restore_session_from_query_params()
    
    def initialize_session_state(self):
        """Initialize session state variables"""
        if 'authenticated' not in st.session_state:
            st.session_state.authenticated = False
        if 'user' not in st.session_state:
            st.session_state.user = None
        if 'mode' not in st.session_state:
            st.session_state.mode = None
        if 'tokens' not in st.session_state:
            st.session_state.tokens = None
        if 'session_id' not in st.session_state:
            # Generate a unique session ID
            import uuid
            st.session_state.session_id = str(uuid.uuid4())
    
    def restore_session_from_query_params(self):
        """Restore session from URL query parameters"""
        # Check if we have session info in query params
        query_params = st.query_params
        
        if 'session_user' in query_params and not st.session_state.authenticated:
            # Restore session
            st.session_state.authenticated = True
            st.session_state.user = query_params['session_user']
            if 'session_mode' in query_params:
                st.session_state.mode = query_params['session_mode']
    
    def persist_session_to_query_params(self):
        """Persist session to URL query parameters"""
        if st.session_state.authenticated:
            st.query_params['session_user'] = st.session_state.user
            if st.session_state.mode:
                st.query_params['session_mode'] = st.session_state.mode
    
    def render_login_page(self):
        """Render login page"""
        # Minimal top spacing
        st.markdown("<div style='padding-top: 5vh;'></div>", unsafe_allow_html=True)
        
        # Compact centered hero section
        st.markdown("""
        <div style="text-align: center; margin-bottom: 2rem;">
            <div style="font-size: 3rem; margin-bottom: 0.5rem;">🚀</div>
            <h1 style="font-size: 2rem; font-weight: 700; background: linear-gradient(135deg, #FF9933 0%, #FF6B35 100%); 
                       -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0.3rem;">
                SageMaker Migration Advisor
            </h1>
            <p style="font-size: 0.95rem; color: #6c757d;">
                AI-powered migration planning
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Centered login form
        col1, col2, col3 = st.columns([1, 1.5, 1])
        
        with col2:
            if not self.auth.enabled:
                st.info("ℹ️ Development mode - enter any credentials")
            
            with st.form("login_form"):
                st.text_input("Username", key="username", placeholder="Enter username")
                st.text_input("Password", type="password", key="password", placeholder="Enter password")
                
                submit = st.form_submit_button("Sign In", use_container_width=True, type="primary")
                
                if submit:
                    username = st.session_state.username
                    password = st.session_state.password
                    
                    if not username or not password:
                        st.error("❌ Please enter both username and password")
                    else:
                        with st.spinner("Authenticating..."):
                            result = self.auth.authenticate(username, password)
                            
                            if result['success']:
                                st.session_state.authenticated = True
                                st.session_state.user = result['user']
                                st.session_state.tokens = result.get('tokens')
                                # Persist session to URL
                                self.persist_session_to_query_params()
                                st.success("✅ Login successful!")
                                st.rerun()
                            else:
                                st.error(f"❌ {result['error']}")
    
    def render_mode_selection(self):
        """Render mode selection page"""
        # Compact hero section
        st.markdown("""
        <div style="text-align: center; padding: 0.5rem 0; margin-bottom: 1rem;">
            <h1 style="font-size: 2rem; font-weight: 700; background: linear-gradient(135deg, #FF9933 0%, #FF6B35 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0.5rem;">🚀 SageMaker Migration Advisor</h1>
            <p style="font-size: 0.95rem; color: #6c757d;">AI-powered ML workload migration to AWS SageMaker</p>
        </div>
        """, unsafe_allow_html=True)
        
        # User info in sidebar
        with st.sidebar:
            st.markdown(f"### 👤 {st.session_state.user}")
            if st.button("🚪 Logout", use_container_width=True):
                self.logout()
            
            st.markdown("---")
            st.markdown("### ℹ️ About")
            st.markdown("""
            AI-powered migration tool with:
            - Automated Analysis
            - TCO Estimation
            - Best Practices
            - Detailed Reports
            """)
        
        # Mode selection
        st.markdown("### Choose Your Migration Path")
        
        col1, col2 = st.columns(2, gap="medium")
        
        with col1:
            # Lite Mode Card
            st.markdown("""
            <div style="padding: 1.5rem; border-radius: 12px; background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%); 
                        border: 2px solid #e9ecef; border-left: 5px solid #17a2b8; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08); 
                        margin-bottom: 0.8rem; height: 280px;">
                <h3 style="font-size: 1.3rem; font-weight: 600; color: #2c3e50; margin-bottom: 0.5rem;">🎯 Lite Mode</h3>
                <p style="font-size: 0.9rem; color: #6c757d; margin-bottom: 1rem; line-height: 1.4;">
                    Quick assessment for streamlined migration planning.
                </p>
                <div style="font-size: 0.85rem; color: #495057;">
                    ✅ Streamlined workflow<br>
                    ✅ Essential analysis<br>
                    ✅ Basic TCO estimation<br>
                    ✅ Fast execution (5-10 min)<br>
                    ✅ PDF report
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            st.info("**Best for:** Quick assessments • Simple migrations")
            
            if st.button("🚀 Launch Lite Mode", key="lite_btn", use_container_width=True, type="primary"):
                st.session_state.mode = 'lite'
                self.persist_session_to_query_params()
                st.rerun()
        
        with col2:
            # Regular Mode Card
            st.markdown("""
            <div style="padding: 1.5rem; border-radius: 12px; background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%); 
                        border: 2px solid #e9ecef; border-left: 5px solid #FF6B35; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08); 
                        margin-bottom: 0.8rem; height: 280px;">
                <h3 style="font-size: 1.3rem; font-weight: 600; color: #2c3e50; margin-bottom: 0.5rem;">🔬 Regular Mode</h3>
                <p style="font-size: 0.9rem; color: #6c757d; margin-bottom: 1rem; line-height: 1.4;">
                    Comprehensive analysis for complex migrations.
                </p>
                <div style="font-size: 0.85rem; color: #495057;">
                    ✅ Multi-agent workflow<br>
                    ✅ Interactive Q&A<br>
                    ✅ Detailed architecture analysis<br>
                    ✅ Comprehensive TCO<br>
                    ✅ Architecture diagrams<br>
                    ✅ Detailed PDF report
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            st.info("**Best for:** Enterprise migrations • Complex workloads")
            
            if st.button("🚀 Launch Regular Mode", key="regular_btn", use_container_width=True, type="primary"):
                st.session_state.mode = 'regular'
                self.persist_session_to_query_params()
                st.rerun()
    
    def render_advisor_app(self):
        """Render the selected advisor mode"""
        # Back button in sidebar
        with st.sidebar:
            st.markdown(f"### 👤 {st.session_state.user}")
            st.markdown(f"**Mode:** {st.session_state.mode.title()}")
            
            if st.button("⬅️ Back to Mode Selection", use_container_width=True):
                st.session_state.mode = None
                st.rerun()
            
            if st.button("🚪 Logout", use_container_width=True):
                self.logout()
        
        # Import and run the appropriate advisor
        if st.session_state.mode == 'lite':
            from sagemaker_migration_advisor_lite import SageMakerAdvisorApp as LiteApp
            app = LiteApp()
            app.run()
        else:
            from sagemaker_migration_advisor import SageMakerAdvisorApp as RegularApp
            app = RegularApp()
            app.run()
    
    def logout(self):
        """Logout user"""
        st.session_state.authenticated = False
        st.session_state.user = None
        st.session_state.mode = None
        st.session_state.tokens = None
        # Clear query params
        st.query_params.clear()
        st.rerun()
    
    def run(self):
        """Main application entry point"""
        if not st.session_state.authenticated:
            self.render_login_page()
        elif st.session_state.mode is None:
            self.render_mode_selection()
        else:
            self.render_advisor_app()


if __name__ == "__main__":
    app = MigrationAdvisorApp()
    app.run()
