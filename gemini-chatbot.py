import google.generativeai as genai
import requests
from typing import List, Dict, Optional, Any
from datetime import datetime

class ProductService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "http://3.146.90.152:2040"
        self.cart_url = "http://3.146.90.152:2070"
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

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
        """Get detailed product information"""
        products_data = self.get_products()
        if not products_data or 'response_body' not in products_data:
            return None

        product_data = products_data['response_body'].get('product_data', [])
        for product in product_data:
            if is_product_id:
                if str(product.get('product_id')) == identifier:
                    return product
            else:
                if str(product.get('product_name', '')).lower() == identifier.lower():
                    return product
        return None

    def get_product_id_by_name(self, product_name: str) -> Optional[str]:
        """Get product ID using product name"""
        product = self.get_product_details(product_name, is_product_id=False)
        if product:
            return str(product.get('product_id'))
        return None

    def validate_pincode(self, pincode: str) -> tuple[bool, List[str]]:
        """Validate pincode and return available product types"""
        products_data = self.get_products()
        if not products_data or 'response_body' not in products_data:
            return False, []

        available_products = []
        is_valid = False
        
        product_data = products_data['response_body'].get('product_data', [])
        for product in product_data:
            if str(pincode) in [str(p) for p in product.get('pin_codes', [])]:
                is_valid = True
                product_type = product.get('product_type_name')
                if product_type and product_type not in available_products:
                    available_products.append(product_type)

        return is_valid, available_products

    def get_slots(self, date: str, product_id: str) -> Optional[Dict]:
        """Fetch slots data from the API"""
        try:
            url = f"{self.base_url}/pbs/rest/v3/slots?date={date}&product_id={product_id}"
            response = requests.get(url, headers=self.headers)
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
        
        for time_period in time_slots:
            day_time_name = time_period.get('day_time_name', '')
            day_slots = time_period.get('day_time_slots', [])
            
            for slot in day_slots:
                if isinstance(slot, dict):
                    slot_info = {
                        'time_period': day_time_name,
                        'start_time': slot.get('slot_start_time'),
                        'end_time': slot.get('slot_end_time'),
                        'duration': slot.get('slot_duration'),
                        'status': slot.get('slot_status')
                    }
                    if all(value is not None for value in slot_info.values()):
                        slot_details.append(slot_info)

        return slot_details

    def get_orders(self) -> Optional[Dict]:
        """Fetch orders from the API"""
        try:
            url = f"{self.cart_url}/cfs/rest/v3/list-orders-with-order-items"
            response = requests.get(url, headers=self.headers)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching orders: {e}")
            return None

    def get_order_details(self) -> str:
        """Get formatted order details"""
        orders_data = self.get_orders()
        if not orders_data or 'response_body' not in orders_data:
            return "No orders found."

        response = "\nYour Orders:\n"
        orders = orders_data['response_body'].get('Orders', [])
        
        if not orders:
            return "You don't have any orders yet."

        for order in orders:
            response += "\n----------------------------------------"
            response += f"\nOrder ID: {order.get('id')}"
            response += f"\nProduct Name: {order.get('product_type_display_name')}"
            response += f"\nOrder Status: {order.get('order_status')}"
            response += f"\nDate: {order.get('date_of_order').split('T')[0]}"
            response += f"\nAmount: {order.get('currency_symbol')} {order.get('total_amount')}"

        return response

    def add_to_cart(self, product_id: str, quantity: int) -> Dict:
        """Add product to cart"""
        try:
            cart_data = {
                "customer_cart": [
                    {
                        "product": int(product_id),
                        "cart_quantity": quantity
                    }
                ]
            }
            
            response = requests.post(
                f"{self.cart_url}/cfs/rest/v3/customer-cart",
                headers=self.headers,
                json=cart_data
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error adding to cart: {e}")
            if hasattr(e, 'response'):
                print(f"Response: {e.response.text}")
            return None

class IntentProcessor:
    def __init__(self, model):
        self.model = model
        self.chat = model.start_chat(history=[])
        
    def process_intent(self, user_input: str) -> Dict[str, Any]:
        """Process user input to understand intent"""
        prompt = f"""Analyze this user input: "{user_input}"
        
        Return a JSON object with these fields:
        1. primary_intent: One of these specific values:
           - SHOW_PRODUCTS (if user wants to see products in a category)
           - SHOW_DETAILS (if user wants details about a specific product)
           - ADD_TO_CART (if user wants to add something to cart)
           - CHECK_ORDERS (if user wants to see order status)
           - CHECK_SLOTS (if user wants to check service slots)
           - NONE (if intent is unclear)
        
        2. category: Product category mentioned (Physical Product/Service Product/Subscription Product)
        3. product_name: Any specific product name mentioned
        4. is_confirmation: true if this is a yes/no response
        5. confirmation_value: true for yes, false for no (only if is_confirmation is true)
        
        Ensure all JSON values are lowercase.
        """
        
        try:
            response = self.chat.send_message(prompt)
            import json
            parsed = json.loads(response.text)
            
            # Ensure all values are lowercase
            for key in parsed:
                if isinstance(parsed[key], str):
                    parsed[key] = parsed[key].lower()
            
            return parsed
        except Exception as e:
            print(f"Error processing intent: {e}")
            return {
                "primary_intent": "none",
                "category": "",
                "product_name": "",
                "is_confirmation": False,
                "confirmation_value": False
            }

class GeminiChatbot:
    def __init__(self):
        genai.configure(api_key="AIzaSyDWdmYNfMRPWdtdt_4jJpUEW8i_xjRqvOM")
        self.model = genai.GenerativeModel('gemini-pro')
        self.intent_processor = IntentProcessor(self.model)
        
        # State management
        self.current_pincode = None
        self.available_product_types = []
        self.current_products = []
        self.current_service_product = None
        self.waiting_for_slot_response = False
        self.waiting_for_date = False
        self.waiting_for_quantity = False
        self.waiting_for_service_cart_response = False
        self.cart_product_name = None
        
        # Initialize API service
        self.product_service = ProductService(api_key="eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJoRl9MajJQQzdYMEZ6UzdsS042RVprZjhabk4tdHU4alREQU9FaEJPLXFnIn0.eyJleHAiOjE3MzYxNzE5NjksImlhdCI6MTczNjEzNTk3MSwiYXV0aF90aW1lIjoxNzM2MTM1OTY5LCJqdGkiOiIyYzFjNTQ1My03ODdlLTQzNDYtYTUzZi1hNTM5ZWQ4ZmZlZjkiLCJpc3MiOiJodHRwczovL2F1dGgudGhtcDkubWFya2V0cGxhY2UudGhic2NvZXRnLmNvbS9yZWFsbXMvR292ZXJubWVudC1jdXN0b21lciIsImF1ZCI6WyJjb3VwbGVyIiwiYWNjb3VudCJdLCJzdWIiOiJkNmM5NTNlNy0xOWExLTRhMjQtOTFhOC1mZmZiZjI5YWQ1YzkiLCJ0eXAiOiJCZWFyZXIiLCJhenAiOiJHb3Zlcm5tZW50LWN1c3RvbWVyLWNsaWVudCIsInNlc3Npb25fc3RhdGUiOiI5NDUzMzJmNS1iYWRlLTQ4YTMtODhhNC01ZTQ5YmQ4MjFjZGIiLCJhY3IiOiIxIiwiYWxsb3dlZC1vcmlnaW5zIjpbIioiXSwicmVhbG1fYWNjZXNzIjp7InJvbGVzIjpbIm9mZmxpbmVfYWNjZXNzIiwiZGVmYXVsdC1yb2xlcy1Hb3Zlcm5tZW50LWN1c3RvbWVyIiwidW1hX2F1dGhvcml6YXRpb24iXX0sInJlc291cmNlX2FjY2VzcyI6eyJhY2NvdW50Ijp7InJvbGVzIjpbIm1hbmFnZS1hY2NvdW50IiwibWFuYWdlLWFjY291bnQtbGlua3MiLCJ2aWV3LXByb2ZpbGUiXX19LCJzY29wZSI6Im9wZW5pZCBzdG9yZV9pZCBlbnRpdHktaWQgZW1haWwgcmVhbG0tbmFtZSBwcm9maWxlIGN1c3RvbWVyX2lkIiwic2lkIjoiOTQ1MzMyZjUtYmFkZS00OGEzLTg4YTQtNWU0OWJkODIxY2RiIiwic3RvcmVfaWQiOiIzIiwiZW1haWxfdmVyaWZpZWQiOnRydWUsIm5hbWUiOiJBaG1lZCBBbC1NYW5zb29yaSIsInByZWZlcnJlZF91c2VybmFtZSI6InZpamF5X3JhY2hha29uZGFAdGhicy5jb20iLCJnaXZlbl9uYW1lIjoiQWhtZWQiLCJyZWFsbS1uYW1lIjoiR292ZXJubWVudC1jdXN0b21lciIsImN1c3RvbWVyX2lkIjoiMyIsImZhbWlseV9uYW1lIjoiQWwtTWFuc29vcmkiLCJlbnRpdHktaWQiOiJHb3Zlcm5tZW50LWN1c3RvbWVyIiwiZW1haWwiOiJ2aWpheV9yYWNoYWtvbmRhQHRoYnMuY29tIn0.GW-ZOdEYV1NIrcKPDX9dbTbr6okGmpZxGu8YuCAGqtgXF0FJwKklUJgUDwCTHCey7dipa1ZBHXya-Z0rZBJKzTYRLpQo2oAKhcDXO9m_CS7es0w6bwOklkXgdZYZzPOaWuw-HK-T83aQRGfxnTwAGw6tP8Khm_M8sH0aYIhitpF83Am7JeiWidMmrYRUj3aPiJKgZFqhaqxaHIdP3bkHCRxIP1Nbgmfq0enlQvz5uG2pz59lpmuKYQJBJOnWqlFvMpGDQRs74QlQZYmY87dzAAj8fwrv26tGZicSsDk_SaCwwSuuWsfYzGEFsqU-Ls5bxTXTC3JviACTFX9eVTu8MSdbOdDe1AnNGzpYmjGhbt4no3jvkzXmw4q5WzrySavVqvZErdz2KVF5t2PMf2MLMZoi9WjU2HxoFtoLdsfkAAIPokdo2myUz66FCKEAC_ECHDkSbgBYeDzxZF54wT9L_VAbOqS5tnF8_QSdVlY6VvRIS9KJtIN7Om6c1Az8ZDg4M2AB_qXiFsdMajnxLbo0MoU-hb9jQvjWMS5KHfTrPmTzhc9hG4HLV9ypkjAPTtGkAsVQO7l-83tp3U1IIEXtXdP9Jl7JUr07t6DAYB3e98jF5Sk_F8baOQizcAJpNTTg7AtQ0J2N6msg7pSOz9cp-LbtvGCj4knzsBqlc8H6MJI")

    def process_query(self, user_input: str) -> str:
        """Process user query"""
        # Get intent data
        intent_data = self.intent_processor.process_intent(user_input)
        
        # Handle state-based responses
        if self.waiting_for_quantity and self.cart_product_name:
            try:
                quantity = int(user_input)
                if quantity <= 0:
                    return "Please enter a valid quantity greater than 0."

                product_id = self.product_service.get_product_id_by_name(self.cart_product_name)
                if not product_id:
                    self.waiting_for_quantity = False
                    self.cart_product_name = None
                    return "Product not found. Please check the product name."

                cart_response = self.product_service.add_to_cart(product_id, quantity)
                self.waiting_for_quantity = False
                self.cart_product_name = None

                if cart_response and cart_response.get('response_message') == 'Item added successfully':
                    return f"Successfully added to your cart!"
                else:
                    return "Sorry, there was an error adding the item to your cart."
            except ValueError:
                return "Please enter a valid number for quantity."

        # Handle yes/no responses
        if intent_data.get('is_confirmation', False):
            if self.waiting_for_slot_response:
                if intent_data.get('confirmation_value', False):
                    self.waiting_for_slot_response = False
                    self.waiting_for_date = True
                    return "Please enter the date (YYYY-MM-DD) to check available slots:"
                else:
                    self.waiting_for_slot_response = False
                    return "No problem. What else would you like to know?"

            if self.waiting_for_service_cart_response:
                if intent_data.get('confirmation_value', False):
                    cart_response = self.product_service.add_to_cart(
                        str(self.current_service_product['product_id']), 1
                    )
                    self.waiting_for_service_cart_response = False
                    if cart_response and cart_response.get('response_message') == 'Item added successfully':
                        return "Great! I've added the service to your cart."
                    else:
                        return "Sorry, there was an error adding the service to your cart."
                else:
                    self.waiting_for_service_cart_response = False
                    return "No problem. What else can I help you with?"

        # Handle date input for slots
        if self.waiting_for_date and self.current_service_product:
            try:
                datetime.strptime(user_input, '%Y-%m-%d')
                slots = self.product_service.get_slot_details(
                    user_input, 
                    str(self.current_service_product['product_id'])
                )
                self.waiting_for_date = False
                
                if not slots:
                    return "No slots available for the selected date."
                
                response = f"\nAvailable slots for {self.current_service_product['product_name']} on {user_input}:"
                current_period = None
                for slot in slots:
                    if current_period != slot['time_period']:
                        current_period = slot['time_period']
                        response += f"\n\n{current_period.upper()}:"
                    response += f"\n{slot['start_time']} - {slot['end_time']} ({slot['duration']} mins)"
                
                response += "\n\nWould you like to add this service to cart?"
                self.waiting_for_service_cart_response = True
                return response
            except ValueError:
                return "Please enter the date in YYYY-MM-DD format (e.g., 2025-01-15)"

        # Process based on intent
        intent = intent_data.get('primary_intent', 'none')
        
        if intent == 'show_products':
            return self.handle_show_products(intent_data.get('category', ''))
            
        elif intent == 'show_details':
            return self.handle_show_details(intent_data.get('product_name', ''))
            
        elif intent == 'add_to_cart':
            return self.handle_add_to_cart(intent_data.get('product_name', ''))
            
        elif intent == 'check_orders':
            return self.product_service.get_order_details()

        return "I'm not sure what you're looking for. You can:\n" + \
               "• Browse products by category\n" + \
               "• Get details about specific products\n" + \
               "• Add items to cart\n" + \
               "• Check your orders"

    def handle_show_products(self, category: str) -> str:
        """Handle show products request"""
        if not category:
            return "What type of products would you like to see? We have Physical Products, Service Products, and Subscription Products."
        
        products_data = self.product_service.get_products()
        if not products_data or 'response_body' not in products_data:
            return "I'm having trouble getting the product information right now."

        filtered_products = []
        for product in products_data['response_body'].get('product_data', []):
            if (product.get('product_type_name').lower() == category.lower() and 
                str(self.current_pincode) in [str(p) for p in product.get('pin_codes', [])]):
                filtered_products.append(product)

        if not filtered_products:
            return f"I don't see any {category}s available in your area right now."

        response = f"\nHere are the available {category}s:\n"
        for product in filtered_products:
            response += f"• {product.get('product_name')}\n"
        response += "\nYou can ask for details about any specific product."
        return response

    def handle_show_details(self, product_name: str) -> str:
        """Handle show details request"""
        product = self.product_service.get_product_details(product_name, is_product_id=False)
        if not product:
            return f"I couldn't find a product named '{product_name}'. Could you check the name?"

        response = ""
        product_type = product.get('product_type_name')

        if product_type == 'Physical Product':
            response = f"Here are the details for {product.get('product_name')}:\n"
            response += f"Price: {product.get('selling_price')}\n"
            response += f"Quantity Available: {product.get('quantity')}\n"
            if product.get('short_description'):
                response += f"Description: {product.get('short_description')}\n"
            response += "\nWould you like to add this to your cart?"
            self.cart_product_name = product_name
            self.waiting_for_quantity = True

        elif product_type == 'Service Product':
            response = f"Here are the details for {product.get('product_name')}:\n"
            response += f"Price: {product.get('selling_price')}\n"
            if product.get('service_details'):
                response += f"Service Details: {product.get('service_details')}\n"
            if product.get('short_description'):
                response += f"Description: {product.get('short_description')}\n"
            response += "\nWould you like to check available slots? (yes/no)"
            self.current_service_product = product
            self.waiting_for_slot_response = True

        return response

    def handle_add_to_cart(self, product_name: str) -> str:
        """Handle add to cart request"""
        if not product_name:
            return "Which product would you like to add to cart?"

        product = self.product_service.get_product_details(product_name, is_product_id=False)
        if not product:
            return f"I couldn't find a product named '{product_name}'. Could you check the name?"

        if product.get('product_type_name') == 'Physical Product':
            self.cart_product_name = product_name
            self.waiting_for_quantity = True
            return f"How many {product_name}s would you like?"
        else:
            return "For services, I'll need to show you available slots first. Would you like to see them?"

    def run(self):
        """Main chatbot loop"""
        print("Hi! I'm your shopping assistant. Let me help you find what you need.")
        
        # Get and validate pincode first
        while True:
            pincode = input("\nPlease enter your 6-digit pincode: ")
            
            if not pincode.isdigit() or len(pincode) != 6:
                print("That doesn't look like a valid pincode. Please enter a 6-digit number.")
                continue

            is_valid, available_products = self.product_service.validate_pincode(pincode)
            
            if not is_valid:
                print("I don't see any products available in your area. Would you like to try another pincode? (yes/no)")
                if input().lower() != 'yes':
                    print("Thanks for visiting! Come back soon!")
                    return
                continue
            
            self.current_pincode = pincode
            self.available_product_types = available_products
            
            print("\nGreat! Here's what's available in your area:")
            for product_type in available_products:
                print(f"• {product_type}")
            print("\nWhat would you like to see first?")
            break

        # Main interaction loop
        while True:
            user_input = input("\nYou: ")
            
            if user_input.lower() in ['exit', 'quit', 'bye']:
                print("Thanks for shopping with us! Have a great day!")
                break

            response = self.process_query(user_input)
            print(f"\nBot: {response}")

def main():
    try:
        chatbot = GeminiChatbot()
        chatbot.run()
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        print("Please try again later.")

if __name__ == "__main__":
    main()