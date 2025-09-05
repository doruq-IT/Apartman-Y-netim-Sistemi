from google.cloud import documentai
from flask import current_app

def process_receipt_from_gcs(gcs_uri: str, processor_id: str, project_id: str, location: str) -> dict:
    """
    Google Cloud Storage'daki bir dekont dosyasını Document AI ile işler
    ve yapılandırılmış veriyi bir sözlük olarak döndürür.
    """
    try:
        # API istemcisini, işlemcinin bulunduğu bölgeye göre oluştur
        opts = {"api_endpoint": f"{location}-documentai.googleapis.com"}
        client = documentai.DocumentProcessorServiceClient(client_options=opts)

        # İşlenecek dosyanın GCS yolunu ve mime türünü belirt
        # Şimdilik en yaygın olanları destekleyelim: pdf, jpg, png
        if gcs_uri.lower().endswith('.pdf'):
            mime_type = 'application/pdf'
        elif gcs_uri.lower().endswith(('.jpg', '.jpeg')):
            mime_type = 'image/jpeg'
        elif gcs_uri.lower().endswith('.png'):
            mime_type = 'image/png'
        else:
            raise ValueError("Desteklenmeyen dosya türü.")

        gcs_document = documentai.GcsDocument(
            gcs_uri=gcs_uri, mime_type=mime_type
        )
        
        # Tam işlemci adını oluştur (API'nin istediği format)
        processor_name = client.processor_path(project_id, location, processor_id)

        # API isteğini oluştur
        request = documentai.ProcessRequest(
            name=processor_name,
            gcs_document=gcs_document,
        )

        # Belgeyi işle ve sonucu al
        result = client.process_document(request=request)
        document = result.document

        # Gerekli bilgileri çıkarmak için boş bir sözlük hazırla
        extracted_data = {}
        for entity in document.entities:
            entity_type = entity.type_
            # Metindeki olası satır sonu karakterlerini temizle
            entity_value = entity.mention_text.replace('\n', ' ').strip()
            
            # İhtiyacımız olan etiketleri kontrol et ve sözlüğe ekle
            if entity_type == 'supplier_name':
                extracted_data['supplier'] = entity_value
            elif entity_type == 'total_amount':
                try:
                    # Tutarı sayısal bir değere (float) çevirmeye çalış
                    extracted_data['amount'] = float(entity_value)
                except (ValueError, TypeError):
                    continue
            elif entity_type == 'receipt_date':
                extracted_data['date'] = entity_value

        current_app.logger.info(f"Document AI'dan çıkarılan veri: {extracted_data}")
        return extracted_data

    except Exception as e:
        # Hata durumunda logla ve None döndür
        current_app.logger.error(f"Document AI işleme hatası: {e}")
        return None