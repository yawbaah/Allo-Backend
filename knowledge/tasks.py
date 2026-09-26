from celery import shared_task
from .services import process_and_index_source as sync_index_source

@shared_task(name="knowledge.tasks.process_and_index_source_task")
def process_and_index_source_task(source_id: str):
    """
    Executes heavy content ingestion, document parsing, website scraping, 
    and vector embedding in the background.
    """
    sync_index_source(source_id)