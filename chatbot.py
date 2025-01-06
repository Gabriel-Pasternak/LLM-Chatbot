import google.generativeai as genai
import requests
from typing import List, Dict, Optional
from datetime import datetime

class ProductService:
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    def get_slots(self, date: str, product_id: str) -> Optional[Dict]:
        """Fetch slots data for a specific date and product"""
        try:
            url = f"{self.base_url}/pbs/rest/v3/slots?date={date}&product_id={product_id}"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching slots: {e}")
            return None

    def get_slot_details(self, date: str, product_id: str) -> List[Dict]:
        """Get formatted slot details"""
        slots_data = self.get_slots(date, product_id)
        if not slots_data or 'response_body' not in slots_data:
            return []

        slot_details = []
        time_slots = slots_data['response_body'].get('slots', [])
        
        for time_slot in time_slots:
            day_time_display_name = time_slot.get('day_time_display_name', '')
            day_time_slots = time_slot.get('day_time_slots', [])
            
            # Process each individual slot in day_time_slots array
            for slot in day_time_slots:
                if isinstance(slot, dict):
                    slot_info = {
                        'time_of_day': day_time_display_name,
                        'start_time': slot.get('slot_start_time'),
                        'duration': slot.get('slot_duration'),
                        'status': slot.get('slot_status'),
                        'is_booked': slot.get('is_booked', False)
                    }
                    if all(value is not None for value in slot_info.values()):
                        slot_details.append(slot_info)

        return slot_details

    def get_products(self) -> Optional[Dict]:
        """Fetch products data from the API"""
        try:
            response = requests.get(
                f"{self.base_url}/pbs/rest/v3/products",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching products: {e}")
            return None

    def get_product_details(self, identifier: str, is_product_id: bool = True) -> Optional[Dict]:
        """Get detailed information for a specific product by ID or name"""
        products_data = self.get_products()
        if not products_data or 'response_body' not in products_data:
            return None

        for product in products_data['response_body'].get('product_data', []):
            if (is_product_id and product.get('product_id') == identifier) or \
               (not is_product_id and product.get('product_name') == identifier):
                return product
        return None

    def get_products_by_type_and_pincode(self, product_type: str, pincode: str) -> List[Dict]:
        """Get products filtered by type and pincode"""
        products_data = self.get_products()
        if not products_data or 'response_body' not in products_data:
            return []

        filtered_products = []
        for product in products_data['response_body'].get('product_data', []):
            if (product.get('product_type_name') == product_type and 
                str(pincode) in [str(p) for p in product.get('pin_codes', [])]):
                filtered_products.append({
                    'product_id': product.get('product_id'),
                    'product_name': product.get('product_name')
                })
        return filtered_products

    def validate_pincode(self, pincode: str) -> tuple[bool, List[str]]:
        """Validate pincode and return available product types"""
        products_data = self.get_products()
        if not products_data or 'response_body' not in products_data:
            return False, []

        available_products = []
        is_valid = False
        
        for product in products_data['response_body'].get('product_data', []):
            if str(pincode) in [str(p) for p in product.get('pin_codes', [])]:
                is_valid = True
                product_type = product.get('product_type_name')
                if product_type and product_type not in available_products:
                    available_products.append(product_type)

        return is_valid, available_products

class GeminiChatbot:
    def __init__(self):
        genai.configure(api_key="AIzaSyDWdmYNfMRPWdtdt_4jJpUEW8i_xjRqvOM")
        self.model = genai.GenerativeModel('gemini-pro')
        self.current_pincode = None
        self.available_product_types = []
        self.current_products = []  # Store current product list for reference
        self.product_service = ProductService(
            api_key="eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJoRl9MajJQQzdYMEZ6UzdsS042RVprZjhabk4tdHU4alREQU9FaEJPLXFnIn0.eyJleHAiOjE3MzYwMDI5NDAsImlhdCI6MTczNTk2Njk0MiwiYXV0aF90aW1lIjoxNzM1OTY2OTQwLCJqdGkiOiI3ODc3NjJkOS0yMWQ1LTQxZGUtYjI4My1hOTcyNGViN2ZmYzQiLCJpc3MiOiJodHRwczovL2F1dGgudGhtcDkubWFya2V0cGxhY2UudGhic2NvZXRnLmNvbS9yZWFsbXMvR292ZXJubWVudC1jdXN0b21lciIsImF1ZCI6WyJjb3VwbGVyIiwiYWNjb3VudCJdLCJzdWIiOiJkNmM5NTNlNy0xOWExLTRhMjQtOTFhOC1mZmZiZjI5YWQ1YzkiLCJ0eXAiOiJCZWFyZXIiLCJhenAiOiJHb3Zlcm5tZW50LWN1c3RvbWVyLWNsaWVudCIsInNlc3Npb25fc3RhdGUiOiI1OGY0ZDkzOC0xYzYwLTQ4MjUtODM4ZC1hNjRjYTExMWUwYzciLCJhY3IiOiIxIiwiYWxsb3dlZC1vcmlnaW5zIjpbIioiXSwicmVhbG1fYWNjZXNzIjp7InJvbGVzIjpbIm9mZmxpbmVfYWNjZXNzIiwiZGVmYXVsdC1yb2xlcy1Hb3Zlcm5tZW50LWN1c3RvbWVyIiwidW1hX2F1dGhvcml6YXRpb24iXX0sInJlc291cmNlX2FjY2VzcyI6eyJhY2NvdW50Ijp7InJvbGVzIjpbIm1hbmFnZS1hY2NvdW50IiwibWFuYWdlLWFjY291bnQtbGlua3MiLCJ2aWV3LXByb2ZpbGUiXX19LCJzY29wZSI6Im9wZW5pZCBzdG9yZV9pZCBlbnRpdHktaWQgZW1haWwgcmVhbG0tbmFtZSBwcm9maWxlIGN1c3RvbWVyX2lkIiwic2lkIjoiNThmNGQ5MzgtMWM2MC00ODI1LTgzOGQtYTY0Y2ExMTFlMGM3Iiwic3RvcmVfaWQiOiIzIiwiZW1haWxfdmVyaWZpZWQiOnRydWUsIm5hbWUiOiJBaG1lZCBBbC1NYW5zb29yaSIsInByZWZlcnJlZF91c2VybmFtZSI6InZpamF5X3JhY2hha29uZGFAdGhicy5jb20iLCJnaXZlbl9uYW1lIjoiQWhtZWQiLCJyZWFsbS1uYW1lIjoiR292ZXJubWVudC1jdXN0b21lciIsImN1c3RvbWVyX2lkIjoiMyIsImZhbWlseV9uYW1lIjoiQWwtTWFuc29vcmkiLCJlbnRpdHktaWQiOiJHb3Zlcm5tZW50LWN1c3RvbWVyIiwiZW1haWwiOiJ2aWpheV9yYWNoYWtvbmRhQHRoYnMuY29tIn0.ktXXbqJuu3qBohZLJYrLiY3ZF7ggjF9OWNEihizntsyCM7dZqpXvgYEl4dONbjYySw6qaZlmWSUOgaP7Ugqrub7yoReVvRoCUrivxKSLnttz4TViFvHC5r9JAwEsAh4gyc1UeXuNJn-HJYKwkQI7YqlbICQQr44dWqxyYRlcBGL9Uy9JYIUDxaaMMzDJUP2sAuLivr6kRGVkV7t35Vi51f1D3cgOpqxF6no4TAgEDLnAReA_SvluILqdixoy40mQRt_BFuD7fECyiw0z951shVPqsxYwiNp29WY1iRp36ZLQOfuPK1akeDyOTyOSIMiCiFV8NC1WehefhpILEx0blQUa-PhZh6-86ZPKhWHbQuoHPDw-f0Re_ghgbhqwQvv_DB1hWWd5P4Fq_fo-CcqrpJtVFhR_0p2FEWZzXIw5tzxWFodObEvbL2AMiCSQCc4KfYcd68CIZlrI6T6aOo9QgcPXWvUtbi1LVxAeEO3HM-1YVwzASoLNWQF2CXKNAkxOGYHB_M-IAhVxnOfpJ44HTjKTrn4Nka4W0Dlx2f6J5qgJn1XQ2JdUetqLWCh0h4hHZNgTfX5IUtG3dgX-sbyMdhqZCSQJeDNhgrmYWEkCNze0HQaFcxhT8XLKOYaP2vNoMDsL17Ft_Z5S6z0nnRQSICrjVo2sqacu5M71gsnia1k",
            base_url="http://3.146.90.152:2040"
        )

    def validate_pincode_input(self, pincode: str) -> bool:
        """Validate if pincode is 6 digits"""
        return pincode.isdigit() and len(pincode) == 6

    def show_product_details(self, identifier: str, is_product_id: bool = True) -> tuple[str, bool]:
        """Display detailed information for a specific product"""
        product = self.product_service.get_product_details(identifier, is_product_id)
        if product:
            details = []
            is_service = False
            
            if product.get('product_type_name') == 'Physical Product':
                # Show specific fields for Physical Products
                fields = ['product_id', 'product_name', 'quantity', 'selling_price', 'short_description']
                for field in fields:
                    value = product.get(field)
                    if value is not None and value != "":
                        details.append(f"{field}: {value}")
                        
            elif product.get('product_type_name') == 'Subscription Product':
                # Show specific fields for Subscription Products
                fields = ['product_id', 'product_name', 'subscription_plan', 'selling_price', 'short_description']
                for field in fields:
                    value = product.get(field)
                    if value is not None and value != "":
                        details.append(f"{field}: {value}")
                        
            elif product.get('product_type_name') == 'Service Product':
                # Show specific fields for Service Products
                fields = ['product_id', 'product_name', 'service_details', 'selling_price', 'short_description']
                for field in fields:
                    value = product.get(field)
                    if value is not None and value != "":
                        details.append(f"{field}: {value}")
                is_service = True
                self.current_service_product = product  # Store the service product
                
            else:
                return "Detailed information is only available for Physical, Subscription, and Service Products.", False
                
            return "\n".join(details), is_service
        return "Product not found.", False

    def process_product_query(self, query: str) -> str:
        """Process queries about products"""
        query_lower = query.lower()
        
        # Handle "show products in <category>" query
        for product_type in self.available_product_types:
            if product_type.lower() in query_lower and "show" in query_lower and "products" in query_lower:
                products = self.product_service.get_products_by_type_and_pincode(
                    product_type, self.current_pincode
                )
                if products:
                    self.current_products = products  # Store current product list
                    response = f"\nProducts for {product_type}:\n"
                    for product in products:
                        response += f"Product ID: {str(product['product_id'])}\nProduct Name: {str(product['product_name'])}\n"
                    response += "\nYou can ask 'show details about <product name/id>' to see more details"
                    return response
                return f"No products found in {product_type} for your pincode."

        # Handle "show details about/of/for <product>" queries
        show_details_phrases = ["show details about", "show details of", "show details for"]
        for phrase in show_details_phrases:
            if phrase in query_lower:
                product_identifier = query_lower.split(phrase)[1].strip()
                if product_identifier:
                    # Check if it matches any product ID or name
                    for product in self.current_products:
                        product_id = str(product['product_id']).lower()
                        product_name = str(product['product_name']).lower()
                        if (product_identifier == product_id or 
                            product_identifier == product_name):
                            details, is_service = self.show_product_details(
                                str(product['product_id']) if product_identifier == product_id 
                                else str(product['product_name']),
                                product_identifier == product_id
                            )
                            if is_service:
                                details += "\n\nWould you like to check available slots for this service? (yes/no)"
                                self.waiting_for_slot_response = True
                            return details
                return "Product not found. Please check the product name or ID."

        # Handle direct product ID or name input
        if self.current_products:
            for product in self.current_products:
                product_id = str(product['product_id']).lower()
                product_name = str(product['product_name']).lower()
                if (query_lower == product_id or query_lower == product_name):
                    details, is_service = self.show_product_details(
                        str(product['product_id']) if query_lower == product_id 
                        else str(product['product_name']),
                        query_lower == product_id
                    )
                    if is_service:
                        details += "\n\nWould you like to check available slots for this service? (yes/no)"
                        self.waiting_for_slot_response = True
                    return details

        # Handle slot-related responses
        if hasattr(self, 'waiting_for_slot_response') and self.waiting_for_slot_response:
            if query_lower == 'yes':
                self.waiting_for_slot_response = False
                self.waiting_for_date = True
                return "Please enter the date (YYYY-MM-DD) to check available slots:"
            elif query_lower == 'no':
                self.waiting_for_slot_response = False
                return "Is there anything else you would like to know about our products?"

        # Handle date input for slots
        if hasattr(self, 'waiting_for_date') and self.waiting_for_date and self.current_service_product:
            try:
                datetime.strptime(query, '%Y-%m-%d')
                slots = self.product_service.get_slot_details(
                    query, 
                    str(self.current_service_product['product_id'])
                )
                self.waiting_for_date = False
                
                if not slots:
                    return "No slots available for the selected date."
                
                response = f"\nAvailable slots for {self.current_service_product['product_name']} on {query}:\n"
                
                # Group slots by time of day
                current_time_of_day = None
                for slot in sorted(slots, key=lambda x: x['start_time']):
                    if current_time_of_day != slot['time_of_day']:
                        current_time_of_day = slot['time_of_day']
                        response += f"\n{current_time_of_day.upper()}:"
                    
                    response += "\n----------------------------------------"
                    response += f"\nStart Time: {slot['start_time']}"
                    response += f"\nDuration: {slot['duration']} minutes"
                    response += f"\nStatus: {slot['status']}"
                    if slot['is_booked']:
                        response += "\nSlot is already booked"
                response += "\n----------------------------------------"
                return response
            except ValueError:
                return "Invalid date format. Please use YYYY-MM-DD format."

        return None

    def run(self):
        """Main chatbot loop"""
        print("Welcome!")
        
        while True:
            pincode = input("\nPlease enter your 6-digit pincode: ")
            
            if not self.validate_pincode_input(pincode):
                print("Invalid pincode format. Please enter a 6-digit number.")
                continue

            is_valid, available_products = self.product_service.validate_pincode(pincode)
            
            if not is_valid:
                print("We don't have products available for your area. Do you still want to browse our catalog? (yes/no): ")
                browse_catalog = input().lower()
                if browse_catalog == 'yes':
                    products_data = self.product_service.get_products()
                    if products_data and 'response_body' in products_data:
                        unique_products = set()
                        for product in products_data['response_body'].get('product_data', []):
                            if 'product_type_name' in product:
                                unique_products.add(product['product_type_name'])
                        if unique_products:
                            print("\nProduct Types Available:")
                            for product_type in unique_products:
                                print(f"{product_type}")
                    break
                else:
                    retry = input("Would you like to try another pincode? (yes/no): ")
                    if retry.lower() != 'yes':
                        print("Thank you for visiting!")
                        exit()
                    continue
            
            self.current_pincode = pincode
            self.available_product_types = available_products
            
            print("\nProduct Types Available for your pincode:")
            for product_type in available_products:
                print(f"{product_type}")
            print("\nType 'show products in <category name>' to see available products")
            break

        while True:
            user_input = input("\nYou: ")
            
            if user_input.lower() == 'exit':
                print("Thank you for visiting!")
                break

            # Process the query
            product_response = self.process_product_query(user_input)
            if product_response:
                print(product_response)
            else:
                print("I don't have any information about that. You can ask me to show products from our available categories.")

def main():
    try:
        chatbot = GeminiChatbot()
        chatbot.run()
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()