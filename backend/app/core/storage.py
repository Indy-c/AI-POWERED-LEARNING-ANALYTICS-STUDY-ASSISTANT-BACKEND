from supabase import Client, create_client

from app.core.config import settings

# Create a Supabase client for backend storage operations
def get_supabase_client() -> Client:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise ValueError("Supabase storage is not configured")
    
    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )