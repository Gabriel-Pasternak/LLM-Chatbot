import google.generativeai as genai
import requests
from typing import List, Dict, Optional
from datetime import datetime

class ProductService:
    def get_orders(self) -> Optional[Dict]:
        """Fetch orders from the API"""
        try:
            response = requests.get(
                "http://3.146.90.152:2070/cfs/rest/v3/list-orders-with-order-items",
                headers=self.headers
            )
            print(f"Orders API Response: {response.text}")  # Debug print
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching orders: {e}")
            return None

    def get_order_details(self) -> List[Dict]:
        """Get formatted order details"""
        orders_data = self.get_orders()
        if not orders_data or 'response_body' not in orders_data:
            return []

        order_details = []
        orders = orders_data['response_body'].get('Orders', [])
        
        for order in orders:
            order_info = {
                'id': order.get('id'),
                'name': order.get('customer_name'),
                'status': order.get('order_status'),
                'order_items_status': order.get('order_items', [])
            }
            order_details.append(order_info)

        return order_details
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
        self.current_pincode = None
        self.available_product_types = []
        self.current_products = []
        self.current_service_product = None
        self.waiting_for_slot_response = False
        self.waiting_for_date = False
        self.waiting_for_quantity = False
        self.cart_product_name = None
        self.product_service = ProductService(api_key="eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJoRl9MajJQQzdYMEZ6UzdsS042RVprZjhabk4tdHU4alREQU9FaEJPLXFnIn0.eyJleHAiOjE3MzYxOTEyMDMsImlhdCI6MTczNjE1NTIwNCwiYXV0aF90aW1lIjoxNzM2MTU1MjAzLCJqdGkiOiJmMjBmOTJjMC00OWM1LTQwMzMtYWViMC0wZDNjNDg3MjllMTIiLCJpc3MiOiJodHRwczovL2F1dGgudGhtcDkubWFya2V0cGxhY2UudGhic2NvZXRnLmNvbS9yZWFsbXMvR292ZXJubWVudC1jdXN0b21lciIsImF1ZCI6WyJjb3VwbGVyIiwiYWNjb3VudCJdLCJzdWIiOiJkNmM5NTNlNy0xOWExLTRhMjQtOTFhOC1mZmZiZjI5YWQ1YzkiLCJ0eXAiOiJCZWFyZXIiLCJhenAiOiJHb3Zlcm5tZW50LWN1c3RvbWVyLWNsaWVudCIsInNlc3Npb25fc3RhdGUiOiJjODYzNjRmMS1kMGMzLTQ4YjQtOGNkNS0xYzhiZDBkZDYyZGYiLCJhY3IiOiIxIiwiYWxsb3dlZC1vcmlnaW5zIjpbIioiXSwicmVhbG1fYWNjZXNzIjp7InJvbGVzIjpbIm9mZmxpbmVfYWNjZXNzIiwiZGVmYXVsdC1yb2xlcy1Hb3Zlcm5tZW50LWN1c3RvbWVyIiwidW1hX2F1dGhvcml6YXRpb24iXX0sInJlc291cmNlX2FjY2VzcyI6eyJhY2NvdW50Ijp7InJvbGVzIjpbIm1hbmFnZS1hY2NvdW50IiwibWFuYWdlLWFjY291bnQtbGlua3MiLCJ2aWV3LXByb2ZpbGUiXX19LCJzY29wZSI6Im9wZW5pZCBzdG9yZV9pZCBlbnRpdHktaWQgZW1haWwgcmVhbG0tbmFtZSBwcm9maWxlIGN1c3RvbWVyX2lkIiwic2lkIjoiYzg2MzY0ZjEtZDBjMy00OGI0LThjZDUtMWM4YmQwZGQ2MmRmIiwic3RvcmVfaWQiOiIzIiwiZW1haWxfdmVyaWZpZWQiOnRydWUsIm5hbWUiOiJBaG1lZCBBbC1NYW5zb29yaSIsInByZWZlcnJlZF91c2VybmFtZSI6InZpamF5X3JhY2hha29uZGFAdGhicy5jb20iLCJnaXZlbl9uYW1lIjoiQWhtZWQiLCJyZWFsbS1uYW1lIjoiR292ZXJubWVudC1jdXN0b21lciIsImN1c3RvbWVyX2lkIjoiMyIsImZhbWlseV9uYW1lIjoiQWwtTWFuc29vcmkiLCJlbnRpdHktaWQiOiJHb3Zlcm5tZW50LWN1c3RvbWVyIiwiZW1haWwiOiJ2aWpheV9yYWNoYWtvbmRhQHRoYnMuY29tIn0.f_GXG7jTvmdcLemnBQmUXnLIYBpO6jIm7U5tME4jcrfq1YdSst4c6Tn0DmDxzXDAJ11QNouBv4Rpm0us4sQGHbM2v_AvKVjAsdLgLCNk6jhTSUvE6ZpUxhU9eOoVKal4gUJbe0-Ej5hgE5V3YCx1sMlP2533AACIq-RFzDGaMePx26BxjjPltAXAABQLwTfq2W-Kgg8vjmBbbzd_9VrDpJ_ZkuG-WW-PfcEgkWfoIqkdxAlPWMXBwTJ9a3GIOUajWGYuUpqQYQw9QTHMnPfu11jG3aIAO6cyJvR5CYVJbSzKmGa_m3wIx4iOIUlnsaqolLog2zB5W_msefXmvapBWJRkFIgiEW6vZS_utg-nUtZhrbpq7u2peCbQ_nPBY5DhR7dS4OjPcisb6D0Ms_mQae5H8h-ad6skHCrgmcWksrqqgAwvgsvQ44YyVYFq90N1Gc3j0orP7nmABUot5Ka9X7jTlhG691t0Cn69BTEwJ_n3_DPO8B9Knyf9tOiynDyOlwi2e-Lt3oMORzqvm6FsjvQcWPV9kdIBSI73wMx4YDW5djM_etT3io7NvxZ_RvxVM8Xnql7ITCG2Xjs1YqsCemA_u70x62BwDpi4ycIoKqmCjEB6u1cDG59-iCIMG2VJQXTn4X1qVPlmtZGfIyy5idzARTjZjM9j2CkOqACjgms")

    def validate_pincode_input(self, pincode: str) -> bool:
        """Validate if pincode is 6 digits"""
        return pincode.isdigit() and len(pincode) == 6

    def understand_intent(self, user_input: str) -> Dict:
        """Use Gemini to understand user intent"""
        try:
            prompt = f"""
            Analyze the user input and identify the intent. Return a JSON response with the following structure:
            {{
                "intent": "one of [get_products, show_details, add_to_cart, check_orders, unknown]",
                "parameters": {{
                    "category": "if mentioned",
                    "product_name": "if mentioned",
                    "quantity": "if mentioned"
                }}
            }}

            Available intents:
            - get_products: User wants to see products in a category
            - show_details: User wants details about a specific product
            - add_to_cart: User wants to add something to cart
            - check_orders: User wants to check order status
            - unknown: Unable to determine intent

            User input: {user_input}
            """

            response = self.model.generate_content(prompt)
            intent_data = response.text.strip()
            # Extract JSON from potential markdown code block
            if "```json" in intent_data:
                intent_data = intent_data.split("```json")[1].split("```")[0].strip()
            elif "```" in intent_data:
                intent_data = intent_data.split("```")[1].strip()
                
            return eval(intent_data)  # Convert string to dict
        except Exception as e:
            print(f"Error understanding intent: {e}")
            return {"intent": "unknown", "parameters": {}}

    def process_natural_query(self, query: str) -> str:
        """Process user query using natural language understanding"""
        if self.waiting_for_quantity:
            return self.handle_quantity_input(query)
        elif self.waiting_for_slot_response:
            return self.handle_slot_response(query)
        elif self.waiting_for_date:
            return self.handle_date_input(query)
        elif self.waiting_for_service_cart_response:
            return self.handle_service_cart_response(query)

        # Use Gemini to understand intent
        intent_data = self.understand_intent(query)
        intent = intent_data.get('intent')
        params = intent_data.get('parameters', {})

        if intent == 'get_products':
            category = params.get('category')
            if not category:
                return "Which category of products would you like to see?"
            return self.handle_show_products(category)
            
        elif intent == 'show_details':
            product_name = params.get('product_name')
            if not product_name:
                return "Which product would you like to know more about?"
            return self.handle_show_details(product_name)
            
        elif intent == 'add_to_cart':
            product_name = params.get('product_name')
            if not product_name:
                return "Which product would you like to add to cart?"
            self.cart_product_name = product_name
            self.waiting_for_quantity = True
            return f"How many {product_name}(s) would you like to purchase?"
            
        elif intent == 'check_orders':
            return self.handle_check_orders()
            
        return "I'm not sure what you're asking for. Could you please rephrase that?"

    def handle_show_products(self, category: str) -> str:
        """Handle showing products in a category"""
        for product_type in self.available_product_types:
            if category.lower() in product_type.lower():
                products = self.product_service.get_products()
                if not products or 'response_body' not in products:
                    return "Error fetching products."

                filtered_products = []
                for product in products['response_body'].get('product_data', []):
                    if (product.get('product_type_name') == product_type and 
                        str(self.current_pincode) in [str(p) for p in product.get('pin_codes', [])]):
                        filtered_products.append(product)

                if filtered_products:
                    self.current_products = filtered_products
                    response = f"\nHere are the {product_type} products available:"
                    for product in filtered_products:
                        response += f"\n- {product.get('product_name')}"
                    return response
        return f"I couldn't find any products in that category."

    def handle_show_details(self, product_name: str) -> str:
        """Handle showing product details"""
        product = self.product_service.get_product_details(product_name, is_product_id=False)
        if not product:
            return "I couldn't find that product. Could you please check the name?"

        details = []
        if product.get('product_type_name') == 'Physical Product':
            fields = ['product_name', 'quantity', 'selling_price', 'short_description']
            for field in fields:
                value = product.get(field)
                if value is not None and value != "":
                    details.append(f"{field}: {value}")
                    
        elif product.get('product_type_name') == 'Service Product':
            fields = ['product_name', 'service_details', 'selling_price', 'short_description']
            for field in fields:
                value = product.get(field)
                if value is not None and value != "":
                    details.append(f"{field}: {value}")
            self.current_service_product = product
            details.append("\nWould you like to check available slots for this service?")
            self.waiting_for_slot_response = True
            
        return "\n".join(details)

    def handle_check_orders(self) -> str:
        """Handle checking order status"""
        orders = self.product_service.get_order_details()
        if not orders:
            return "I couldn't find any orders."
        
        response = "\nHere are your orders:"
        for order in orders:
            response += f"\n\nOrder ID: {order['id']}"
            response += f"\nCustomer Name: {order['name']}"
            response += f"\nOrder Status: {order['status']}"
            
            if order.get('order_items_status'):
                response += "\nOrder Items Status:"
                for item in order['order_items_status']:
                    response += f"\n- {item.get('name')}: {item.get('status')}"
            
            response += "\n----------------------------------------"
        
        return response

        # Handle "show products in <category>" query
        for product_type in self.available_product_types:
            if product_type.lower() in query_lower and "show" in query_lower and "products" in query_lower:
                products_data = self.product_service.get_products()
                if not products_data or 'response_body' not in products_data:
                    return "Error fetching products."

                filtered_products = []
                for product in products_data['response_body'].get('product_data', []):
                    if (product.get('product_type_name') == product_type and 
                        str(self.current_pincode) in [str(p) for p in product.get('pin_codes', [])]):
                        filtered_products.append(product)

                if filtered_products:
                    self.current_products = filtered_products
                    response = f"\nProducts for {product_type}:\n"
                    for product in filtered_products:
                        response += f"Product Name: {product.get('product_name')}\n"
                    if product_type == "Physical Product":
                        response += "\nTo add a product to cart, type 'add to cart <product name>'"
                    response += "\nFor more details, type 'show details about <product name>'"
                    return response
                return f"No products found in {product_type} for your pincode."

        # Handle "add to cart" command
        if query_lower.startswith('add to cart'):
            product_name = query_lower.replace('add to cart', '').strip()
            product = self.product_service.get_product_details(product_name, is_product_id=False)
            if not product:
                return "Product not found. Please check the product name."
            if product.get('product_type_name') != 'Physical Product':
                return "Sorry, only physical products can be added to cart."
            self.cart_product_name = product_name
            self.waiting_for_quantity = True
            return f"Please enter the quantity for {product_name}:"

        # Handle quantity input for cart
        if self.waiting_for_quantity and self.cart_product_name:
            try:
                quantity = int(query)
                if quantity <= 0:
                    return "Please enter a valid quantity greater than 0."
                product_id = self.product_service.get_product_id_by_name(self.cart_product_name)
                if not product_id:
                    self.waiting_for_quantity = False
                    self.cart_product_name = None
                    return "Product not found. Please check the product name."

                cart_response = self.product_service.add_to_cart(product_id, quantity)
                self.waiting_for_quantity = False
                product_name = self.cart_product_name
                self.cart_product_name = None

                if cart_response:
                    if cart_response.get('status_code') == '409':
                        return cart_response.get('response_message')
                    elif cart_response.get('response_message') == 'Item added successfully':
                        return f"Successfully added {quantity} {product_name}(s) to your cart."
                    else:
                        return cart_response.get('response_message', 'Failed to add item to cart.')
                return "Sorry, there was an error adding the item to your cart. Please try again."
            except ValueError:
                return "Please enter a valid number for quantity."

        # Handle "show details about" queries with various formats
        show_details_variations = [
            "show details about",
            "show details of",
            "show details for",
            "show detatils about",
            "show detail about",
            "details about",
            "details of",
            "show details"
        ]
        
        for phrase in show_details_variations:
            if phrase in query_lower:
                product_name = query_lower.replace(phrase, "").strip()
                product = self.product_service.get_product_details(product_name, is_product_id=False)
                if not product:
                    return "Product not found. Please check the product name."
                
                details = []
                if product.get('product_type_name') == 'Physical Product':
                    fields = ['product_id', 'product_name', 'quantity', 'selling_price', 'short_description']
                    for field in fields:
                        value = product.get(field)
                        if value is not None and value != "":
                            details.append(f"{field}: {value}")
                    details.append("\nTo add this product to cart, type 'add to cart <product name>'")
                    
                elif product.get('product_type_name') == 'Service Product':
                    fields = ['product_id', 'product_name', 'service_details', 'selling_price', 'short_description']
                    for field in fields:
                        value = product.get(field)
                        if value is not None and value != "":
                            details.append(f"{field}: {value}")
                    self.current_service_product = product
                    details.append("\nWould you like to check available slots for this service? (yes/no)")
                    self.waiting_for_slot_response = True
                    
                return "\n".join(details)

        # Handle "yes/no" response for slot checking
        if self.waiting_for_slot_response:
            if query_lower == 'yes':
                self.waiting_for_slot_response = False
                self.waiting_for_date = True
                return "Please enter the date (YYYY-MM-DD) to check available slots:"
            elif query_lower == 'no':
                self.waiting_for_slot_response = False
                return "Is there anything else you would like to know about our products?"

        # Handle date input for slots
        if self.waiting_for_date and self.current_service_product:
            try:
                datetime.strptime(query, '%Y-%m-%d')
                slots = self.product_service.get_slot_details(query, str(self.current_service_product['product_id']))
                self.waiting_for_date = False
                
                if not slots:
                    return "No slots available for the selected date."
                
                response = f"\nAvailable slots for {self.current_service_product['product_name']} on {query}:"
                
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
                
                response += "\n\nWould you like to add this service to cart? (yes/no)"
                self.waiting_for_service_cart_response = True
                return response
            except ValueError:
                return "Invalid date format. Please use YYYY-MM-DD format."

        # Handle service cart response
        if hasattr(self, 'waiting_for_service_cart_response') and self.waiting_for_service_cart_response:
            if query_lower == 'yes':
                self.waiting_for_service_cart_response = False
                # Add service to cart with quantity 1
                cart_response = self.product_service.add_to_cart(
                    str(self.current_service_product['product_id']), 1
                )
                
                if cart_response:
                    if cart_response.get('status_code') == '409':
                        return cart_response.get('response_message')
                    elif cart_response.get('response_message') == 'Item added successfully':
                        return f"Successfully added {self.current_service_product['product_name']} to your cart."
                    else:
                        return cart_response.get('response_message', 'Failed to add service to cart.')
                return "Sorry, there was an error adding the service to your cart. Please try again."
            elif query_lower == 'no':
                self.waiting_for_service_cart_response = False
                return "Is there anything else you would like to know about our products?"

        if any(word in query_lower for word in ['detail', 'details']):
            return "To see product details, type 'show details about <product name>'"

        return "I don't understand that command. You can:\n- Show products in a category\n- Show details about a product\n- Add products to cart"

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
                print("We don't have products available for your area. Would you like to try another pincode? (yes/no): ")
                retry = input().lower()
                if retry != 'yes':
                    print("Thank you for visiting!")
                    break
                continue
            
            self.current_pincode = pincode
            self.available_product_types = available_products
            
            print("\nProduct Types Available for your pincode:")
            for product_type in available_products:
                print(f"- {product_type}")
            print("\nType 'show products in <category>' to see available products")
            break

        while True:
            user_input = input("\nYou: ")
            
            if user_input.lower() == 'exit':
                print("Thank you for visiting!")
                break

            response = self.process_product_query(user_input)
            print(f"\nBot: {response}")

def main():
    try:
        chatbot = GeminiChatbot()
        chatbot.run()
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()