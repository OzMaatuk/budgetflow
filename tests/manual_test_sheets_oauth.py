"""Test Google Sheets API access using OAuth 2.0 user authentication."""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils.auth import get_credentials
import gspread

def test_sheets_with_oauth():
    """Test if user account can create sheets using OAuth 2.0."""
    print("Testing Google Sheets API access with OAuth 2.0...")
    print("-" * 50)
    
    # Check if client_secrets.json exists
    if not Path("client_secrets.json").exists():
        print("\n✗ ERROR: 'client_secrets.json' not found!")
        print("\nTo create it:")
        print("  1. Go to: https://console.cloud.google.com/apis/credentials")
        print("  2. Configure OAuth consent screen and add yourself as test user")
        print("  3. Click 'Create Credentials' > 'OAuth client ID'")
        print("  4. Choose 'Desktop app' as application type")
        print("  5. Download the JSON file and save it as 'client_secrets.json'")
        print("\nSee docs/USER_GUIDE.md for detailed instructions")
        return
    
    try:
        # Get credentials using the auth module
        print("\n⚠ First-time setup: A browser window will open for authorization")
        print("  Make sure you added yourself as a test user in OAuth consent screen")
        
        creds = get_credentials(
            oauth_client_secrets="client_secrets.json",
            oauth_token_path="token.pickle"
        )
        print("✓ OAuth credentials obtained")
        
        # Authorize gspread client
        client = gspread.authorize(creds)
        print("✓ gspread client authorized")
    except Exception as e:
        print(f"✗ Failed to get credentials: {e}")
        return
    
    # Folder ID where the sheet will be created
    folder_id = '1r9kwBXl5yKttFT14kBUUIsXS8MZQ3CAQ'
    
    spreadsheet = None
    try:
        # Create the spreadsheet in the specified folder
        print(f"\nCreating spreadsheet in folder: {folder_id}...")
        spreadsheet = client.create("BudgetFlow_Test_Sheet_OAuth", folder_id=folder_id)
        
        print(f"✓ Spreadsheet created successfully!")
        print(f"  Title: {spreadsheet.title}")
        print(f"  ID: {spreadsheet.id}")
        print(f"  URL: {spreadsheet.url}")
        
    except Exception as e:
        print(f"✗ Failed to create spreadsheet: {e}")
        
        # Check if it's a quota error
        error_str = str(e).lower()
        if 'quota' in error_str or 'storage' in error_str:
            print("\n🛑 STORAGE QUOTA EXCEEDED:")
            print("  Your Google Drive storage is full!")
            print("  Free up space or upgrade your storage plan.")
        elif 'permission' in error_str or '403' in error_str:
            print("\n⚠ PERMISSION ISSUE:")
            print("  Make sure you have write access to the target folder.")
        return
    
    finally:
        # Clean up - delete the test spreadsheet
        if spreadsheet:
            print("\nCleaning up test spreadsheet...")
            try:
                client.del_spreadsheet(spreadsheet.id)
                print("✓ Test spreadsheet deleted")
            except Exception as e:
                print(f"⚠ Could not delete test sheet: {e}")
    
    print("\n" + "=" * 50)
    print("✓ ALL TESTS PASSED!")
    print("Your Google Sheets API access is working correctly.")
    print("\nNote: Future runs will use saved credentials (no browser popup).")

if __name__ == "__main__":
    test_sheets_with_oauth()
