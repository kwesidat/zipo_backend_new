import os
from supabase import create_client, Client
from dotenv import load_dotenv

#load environment variables from a .env file
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

if not all([SUPABASE_URL, SUPABASE_KEY, SUPABASE_BUCKET, SUPABASE_JWT_SECRET]):
    raise ValueError("Missing one or more required environment variables: SUPABASE_URL, SUPABASE_KEY, SUPABASE_BUCKET")

#Initialize the Supabase client with service role key (for backend operations)
if SUPABASE_SERVICE_ROLE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
else:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize Prisma client - will be lazy loaded
prisma = None

async def get_prisma():
    """Get or initialize Prisma client"""
    global prisma
    if prisma is None:
        try:
            from prisma import Prisma
            prisma = Prisma()
        except RuntimeError as e:
            if "Client hasn't been generated" in str(e):
                print("Warning: Prisma client not generated. Using Supabase only.")
                return None
            raise
    return prisma

async def connect_db():
    """Connect to the database"""
    try:
        db = await get_prisma()
        if db:
            await db.connect()
            print("Database connection established (Prisma + Supabase)")
        else:
            print("Database connection established (Supabase only)")
    except Exception as e:
        print(f"Database connection warning: {e}")
        print("Continuing with Supabase only")

async def disconnect_db():
    """Disconnect from the database"""
    try:
        if prisma:
            await prisma.disconnect()
            print("Database connection closed")
    except Exception as e:
        print(f"Database disconnection warning: {e}")