"""
Shopping Assistant Chatbot using Google Gemini
"""

import google.generativeai as genai
import requests
import json
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
            print(f"Fetching slots from: {url}")
            response = requests.get(url, headers=self.headers)
            print(f"Slots API Response: {response.text}")
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
            print(f"Orders API Response: {response.text}")
            response.raise_for_status()
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


class GeminiChatbot:
    def __init__(self):
        genai.configure(api_key="AIzaSyDWdmYNfMRPWdtdt_4jJpUEW8i_xjRqvOM")
        self.model = genai.GenerativeModel('gemini-pro')
        self.chat = self.model.start_chat(history=[])
        
        # State management
        self.current_pincode = None
        self.available_product_types = []
        self.current_service_product = None
        self.waiting_for_slot_response = False
        self.waiting_for_date = False
        self.waiting_for_quantity = False
        self.cart_product_name = None
        
        # Initialize API service
        self.product_service = ProductService(api_key="eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJoRl9MajJQQzdYMEZ6UzdsS042RVprZjhabk4tdHU4alREQU9FaEJPLXFnIn0.eyJleHAiOjE3MzYxNzE5NjksImlhdCI6MTczNjEzNTk3MSwiYXV0aF90aW1lIjoxNzM2MTM1OTY5LCJqdGkiOiIyYzFjNTQ1My03ODdlLTQzNDYtYTUzZi1hNTM5ZWQ4ZmZlZjkiLCJpc3MiOiJodHRwczovL2F1dGgudGhtcDkubWFya2V0cGxhY2UudGhic2NvZXRnLmNvbS9yZWFsbXMvR292ZXJubWVudC1jdXN0b21lciIsImF1ZCI6WyJjb3VwbGVyIiwiYWNjb3VudCJdLCJzdWIiOiJkNmM5NTNlNy0xOWExLTRhMjQtOTFhOC1mZmZiZjI5YWQ1YzkiLCJ0eXAiOiJCZWFyZXIiLCJhenAiOiJHb3Zlcm5tZW50LWN1c3RvbWVyLWNsaWVudCIsInNlc3Npb25fc3RhdGUiOiI5NDUzMzJmNS1iYWRlLTQ4YTMtODhhNC01ZTQ5YmQ4MjFjZGIiLCJhY3IiOiIxIiwiYWxsb3dlZC1vcmlnaW5zIjpbIioiXSwicmVhbG1fYWNjZXNzIjp7InJvbGVzIjpbIm9mZmxpbmVfYWNjZXNzIiwiZGVmYXVsdC1yb2xlcy1Hb3Zlcm5tZW50LWN1c3RvbWVyIiwidW1hX2F1dGhvcml6YXRpb24iXX0sInJlc291cmNlX2FjY2VzcyI6eyJhY2NvdW50Ijp7InJvbGVzIjpbIm1hbmFnZS1hY2NvdW50IiwibWFuYWdlLWFjY291bnQtbGlua3MiLCJ2aWV3LXByb2ZpbGUiXX19LCJzY29wZSI6Im9wZW5pZCBzdG9yZV9pZCBlbnRpdHktaWQgZW1haWwgcmVhbG0tbmFtZSBwcm9maWxlIGN1c3RvbWVyX2lkIiwic2lkIjoiOTQ1MzMyZjUtYmFkZS00OGEzLTg4YTQtNWU0OWJkODIxY2RiIiwic3RvcmVfaWQiOiIzIiwiZW1haWxfdmVyaWZpZWQiOnRydWUsIm5hbWUiOiJBaG1lZCBBbC1NYW5zb29yaSIsInByZWZlcnJlZF91c2VybmFtZSI6InZpamF5X3JhY2hha29uZGFAdGhicy5jb20iLCJnaXZlbl9uYW1lIjoiQWhtZWQiLCJyZWFsbS1uYW1lIjoiR292ZXJubWVudC1jdXN0b21lciIsImN1c3RvbWVyX2lkIjoiMyIsImZhbWlseV9uYW1lIjoiQWwtTWFuc29vcmkiLCJlbnRpdHktaWQiOiJHb3Zlcm5tZW50LWN1c3RvbWVyIiwiZW1haWwiOiJ2aWpheV9yYWNoYWtvbmRhQHRoYnMuY29tIn0.GW-ZOdEYV1NIrcKPDX9dbTbr6okGmpZxGu8YuCAGqtgXF0FJwKklUJgUDwCTHCey7dipa1ZBHXya-Z0rZBJKzTYRLpQo2oAKhcDXO9m_CS7es0w6bwOklkXgdZYZzPOaWuw-HK-T83aQRGfxnTwAGw6tP8Khm_M8sH0aYIhitpF83Am7JeiWidMmrYRUj3aPiJKgZFqhaqxaHIdP3bkHCRxIP1Nbgmfq0enlQvz5uG2pz59lpmuKYQJBJOnWqlFvMpGDQRs74QlQZYmY87dzAAj8fwrv26tGZicSsDk_SaCwwSuuWsfYzGEFsqU-Ls5bxTXTC3JviACTFX9eVTu8MSdbOdDe1AnNGzpYmjGhbt4no3jvkzXmw4q5WzrySavVqvZErdz2KVF5t2PMf2MLMZoi9WjU2HxoFtoLdsfkAAIPokdo2myUz66FCKEAC_ECHDkSbgBYeDzxZF54wT9L_VAbOqS5tnF8_QSdVlY6VvRIS9KJtIN7Om6c1Az8ZDg4M2AB_qXiFsdMajnxLbo0MoU-hb9jQvjWMS5KHfTrPmTzhc9hG4HLV9ypkjAPTtGkAsVQO7l-83tp3U1IIEXtXdP9Jl7JUr07t6DAYB3e98jF5Sk_F8baOQizcAJpNTTg7AtQ0J2N6msg7pSOz9cp-LbtvGCj4knzsBqlc8H6MJI")

    def process_query(self, query: str) -> str:
        """Process user query and generate response"""
        # Process intent using Gemini
        prompt = f"""Given the user query: "{query}"
        Identify the main intent:
        1. show_products - if user wants to see products in a category
        2. show_details - if user wants product details
        3. add_to_cart - if user wants to add products
        4. check_orders - if user wants to see orders
        5. check_slots - if user wants to check service slots
        
        Extract relevant information like product names or categories.
        
        Return ONLY:
        1. The intent (from above list)
        2. Any product/category name mentioned
        """
        
        try:
            response = self.chat.send_message(prompt)
            intent_info = response.text.strip().split('\n')
            intent = intent_info[0].lower()
            item = intent_info[1].lower() if len(intent_info) > 1 else ""
            
            # Handle different intents
            if "show_products" in intent:
                return self.handle_show_products(item)
            elif "show_details" in intent:
                return self.handle_show_details(item)
            elif "add_to_cart" in intent:
                return self.handle_add_to_cart(item)
            elif "check_orders" in intent:
                return self.handle_check_orders()
            elif "check_slots" in intent and self.current_service_product:
                self.waiting_for_date = True
                return "Please enter the date (YYYY-MM-DD) to check available slots:"
            
            # Handle state-based inputs
            return self.handle_state_based_input(query)
            
        except Exception as e:
            print(f"Error processing query: {e}")
            return "I'm having trouble understanding that. Could you try rephrasing?"

    def handle_state_based_input(self, user_input: str) -> str:
        """Handle inputs based on current state"""
        if self.waiting_for_date and self.current_service_product:
            try:
                date = datetime.strptime(user_input, '%Y-%m-%d')
                return self.handle_slot_check(user_input)
            except ValueError:
                return "Please enter the date in YYYY-MM-DD format (e.g., 2025-01-15)"

        if self.waiting_for_quantity and self.cart_product_name:
            try:
                quantity = int(user_input)
                if quantity <= 0:
                    return "Please enter a valid quantity greater than 0."
                return self.handle_add_to_cart_with_quantity(quantity)
            except ValueError:
                return "Please enter a valid number for quantity."

        if user_input.lower() == 'yes':
            if self.waiting_for_slot_response:
                self.waiting_for_slot_response = False
                self.waiting_for_date = True
                return "Please enter the date (YYYY-MM-DD) to check available slots:"

        return None

    def handle_show_products(self, category: str) -> str:
        """Handle showing products by category"""
        for product_type in self.available_product_types:
            if category.lower() in product_type.lower():
                products_data = self.product_service.get_products()
                if not products_data:
                    return "Sorry, I'm having trouble accessing the products right now."

                filtered_products = []
                for product in products_data['response_body'].get('product_data', []):
                    if (product.get('product_type_name') == product_type and 
                        str(self.current_pincode) in [str(p) for p in product.get('pin_codes', [])]):
                        filtered_products.append(product)

                if filtered_products:
                    response = f"\nHere are the {product_type}s available in your area:\n"
                    for product in filtered_products:
                        response += f"• {product.get('product_name')}\n"
                    response += "\nYou can ask me for more details about any of these products."
                    return response
                
                return f"I couldn't find any {product_type}s available in your area right now."

        return "Please specify which type of product you're interested in: Physical Product, Service Product, or Subscription Product."

    def handle_show_details(self, product_name: str) -> str:
        """Handle showing product details"""
        product = self.product_service.get_product_details(product_name, is_product_id=False)
        if not product:
            return f"I couldn't find any product named '{product_name}'. Could you please check the name?"

        response = "\nProduct Details:\n"
        
        if product.get('product_type_name') == 'Physical Product':
            fields = ['product_name', 'quantity', 'selling_price', 'short_description']
            for field in fields:
                if product.get(field):
                    response += f"{field.replace('_', ' ').title()}: {product[field]}\n"
            response += "\nYou can add this to your cart by saying 'add to cart'."
            
        elif product.get('product_type_name') == 'Service Product':
            fields = ['product_name', 'service_details', 'selling_price', 'short_description']
            for field in fields:
                if product.get(field):
                    response += f"{field.replace('_', ' ').title()}: {product[field]}\n"
            response += "\nWould you like to check available slots? (yes/no)"
            self.current_service_product = product
            self.waiting_for_slot_response = True
            
        return response

    def handle_add_to_cart(self, product_name: str) -> str:
        """Handle adding item to cart"""
        product = self.product_service.get_product_details(product_name, is_product_id=False)
        if not product:
            return f"I couldn't find a product named '{product_name}'. Could you please check the name?"

        if product.get('product_type_name') != 'Physical Product':
            return "For services, I'll need to show you available slots first. Would you like to see them?"

        self.cart_product_name = product_name
        self.waiting_for_quantity = True
        return f"How many {product_name}s would you like?"

    def handle_add_to_cart_with_quantity(self, quantity: int) -> str:
        """Handle adding item to cart with specified quantity"""
        product_id = self.product_service.get_product_details(self.cart_product_name, is_product_id=False)['product_id']
        cart_response = self.product_service.add_to_cart(str(product_id), quantity)
        
        self.waiting_for_quantity = False
        self.cart_product_name = None
        
        if cart_response and cart_response.get('response_message') == 'Item added successfully':
            return f"Great! I've added {quantity} {self.cart_product_name}(s) to your cart."
        return "Sorry, I couldn't add the item to your cart. Please try again."

    def handle_check_orders(self) -> str:
        """Handle checking orders"""
        return self.product_service.get_order_details()

    def handle_slot_check(self, date: str) -> str:
        """Handle checking service slots"""
        slots = self.product_service.get_slot_details(
            date, 
            str(self.current_service_product['product_id'])
        )
        self.waiting_for_date = False
        
        if not slots:
            return "No slots available for that date. Would you like to try another date?"
        
        response = f"\nAvailable slots for {self.current_service_product['product_name']} on {date}:"
        
        # Group slots by time period
        current_period = None
        for slot in slots:
            if current_period != slot['time_period']:
                current_period = slot['time_period']
                response += f"\n\n{current_period.upper()}:"
            
            response += "\n----------------------------------------"
            response += f"\nStart Time: {slot['start_time']}"
            response += f"\nEnd Time: {slot['end_time']}"
            response += f"\nDuration: {slot['duration']} minutes"
            response += f"\nStatus: {slot['status']}"

        response += "\n\nWould you like to book this service? (yes/no)"
        return response

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
            print("\nYou can:")
            print("• Browse products by saying 'show products in <category>'")
            print("• Get details by saying 'tell me about <product name>'")
            print("• Check your orders by saying 'show my orders'")
            break

        # Main interaction loop
        while True:
            user_input = input("\nYou: ")
            
            if user_input.lower() in ['exit', 'quit', 'bye']:
                print("Thanks for shopping with us! Have a great day!")
                break

            response = self.process_query(user_input)
            if response:
                print(f"\nBot: {response}")
            else:
                print("\nBot: I'm not sure about that. You can:")
                print("• Browse products by saying 'show products in <category>'")
                print("• Get details by saying 'tell me about <product name>'")
                print("• Check your orders by saying 'show my orders'")


def main():
    try:
        chatbot = GeminiChatbot()
        chatbot.run()
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        print("Please try again later.")

if __name__ == "__main__":
    main()