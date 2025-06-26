import os
import json
import gspread
import tempfile

def _get_gspread_client_production():
    """
    Hàm kết nối Google Sheets cho production.
    Ưu tiên sử dụng GCP_CREDENTIALS_JSON từ environment variable.
    """
    try:
        # Thử đọc từ environment variable trước
        gcp_credentials_json = os.getenv('GCP_CREDENTIALS_JSON')
        
        if gcp_credentials_json:
            print("Sử dụng credentials từ environment variable")
            # Parse JSON string từ environment variable
            credentials_dict = json.loads(gcp_credentials_json)
            
            # Tạo temporary file để gspread có thể đọc
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
                json.dump(credentials_dict, temp_file)
                temp_file_path = temp_file.name
            
            return gspread.service_account(filename=temp_file_path)
        
        # Fallback về file local nếu có
        local_creds_path = os.getenv("GCP_CREDS_FILE_PATH", "gcp_credentials.json")
        if os.path.exists(local_creds_path):
            print(f"Sử dụng credentials từ file local: {local_creds_path}")
            return gspread.service_account(filename=local_creds_path)
        
        raise Exception("Không tìm thấy Google credentials")
        
    except Exception as e:
        print(f"Lỗi khi kết nối Google Sheets: {e}")
        raise

def get_gspread_client_safe(gcp_creds_file_path=None):
    """
    Wrapper function để tự động chọn phương thức kết nối phù hợp
    """
    # Kiểm tra nếu đang chạy trong production (có GCP_CREDENTIALS_JSON)
    if os.getenv('GCP_CREDENTIALS_JSON'):
        return _get_gspread_client_production()
    
    # Nếu không, sử dụng file path truyền vào
    if gcp_creds_file_path and os.path.exists(gcp_creds_file_path):
        return gspread.service_account(filename=gcp_creds_file_path)
    
    # Cuối cùng, thử production method
    return _get_gspread_client_production()
