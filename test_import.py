import sys
print('Importing fastapi...', flush=True)
import fastapi
print('Importing config...', flush=True)
from src.config import get_settings
print('Importing pool...', flush=True)
from src.db.pool import get_async_pool
print('Importing routers...', flush=True)
from src.routers import health
print('Imported health', flush=True)
from src.routers import chat
print('Imported chat', flush=True)
from src.routers import ingest
print('Imported ingest', flush=True)
from src.routers import test_ui
print('Imported test_ui', flush=True)
from src.routers import evidence
print('Imported evidence', flush=True)
from src.routers import upload
print('Imported upload', flush=True)
from src.routers import documents
print('Imported documents', flush=True)
from src.routers import citation
print('Imported citation', flush=True)
from src.routers import policy_brief
print('Imported policy_brief', flush=True)
from src.routers.thaijo import router as thaijo_router
print('Imported thaijo_router', flush=True)
print('Done', flush=True)
