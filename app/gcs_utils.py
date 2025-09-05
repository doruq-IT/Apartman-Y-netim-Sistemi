# app/gcs_utils.py

from google.cloud import storage
from flask import current_app
import uuid

def upload_to_gcs(file_to_upload, folder_name, return_gcs_uri=False):
    """
    Bir dosyayı GCS'e yükler.
    return_gcs_uri True ise GCS URI'ını, değilse public URL'i döndürür.
    """
    try:
        storage_client = storage.Client()
        bucket_name = current_app.config.get('GCS_BUCKET_NAME')
        if not bucket_name:
            raise ValueError("GCS_BUCKET_NAME konfigürasyonda ayarlanmamış.")
            
        bucket = storage_client.bucket(bucket_name)

        unique_filename = f"{folder_name}/{uuid.uuid4().hex}-{file_to_upload.filename}"
        
        blob = bucket.blob(unique_filename)
        blob.upload_from_file(file_to_upload, content_type=file_to_upload.content_type)

        # === YENİ EKLENEN KONTROL ===
        if return_gcs_uri:
            # Document AI'ın istediği format: gs://bucket_adi/dosya_adi
            return f"gs://{bucket_name}/{unique_filename}"
        
        # Varsayılan olarak, mevcut kod gibi public URL'i döndür
        return blob.public_url

    except Exception as e:
        current_app.logger.error(f"GCS Yükleme Hatası: {e}", exc_info=True)
        return None