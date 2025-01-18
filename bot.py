import google.generativeai as genai
import requests
from typing import List, Dict, Optional
from datetime import datetime

class ProductService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "http://3.90.152:2040"
        self.cart_url = "http://3.90.152:2070"
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    def get_orders(self) -> Optional[Dict]:
        """Fetch orders data from the API"""
        try:
            url = f"{self.cart_url}/cfs/rest/v3/list-orders-with-order-items"
            response = requests.get(url, headers=self.headers)
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
                'product_name': order.get('product_type_name'),
                'order_status': order.get('order_status'),
                'date_of_order': order.get('date_of_order')
            }
            if all(value is not None for value in order_info.values()):
                order_details.append(order_info)

        return order_details

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
        genai.configure(api_key="AIzaSyDWdmY")
        self.model = genai.GenerativeModel('gemini-pro')
        self.current_pincode = None
        self.available_product_types = []
        self.current_products = []
        self.current_service_product = None
        self.waiting_for_slot_response = False
        self.waiting_for_date = False
        self.waiting_for_quantity = False
        self.cart_product_name = None
        self.product_service = ProductService(api_key="eyJhbGciOiJSUzI1NiIsI")

    def validate_pincode_input(self, pincode: str) -> bool:
        """Validate if pincode is 6 digits"""
        return pincode.isdigit() and len(pincode) == 6

    def process_product_query(self, query: str) -> str:
        """Process queries about products"""
        query_lower = query.lower()

        # Handle order status request
        if "order status" in query_lower or "my orders" in query_lower:
            orders = self.product_service.get_order_details()
            if not orders:
                return "No orders found."
            
            response = "\nYour Orders:"
            for order in orders:
                response += "\n----------------------------------------"
                response += f"\nOrder ID: {order['id']}"
                response += f"\nProduct: {order['product_name']}"
                response += f"\nStatus: {order['order_status']}"
                response += f"\nOrder Date: {order['date_of_order']}"
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
                    if cart_response.get('response_message') == 'Item added successfully':
                        return f"Successfully added {quantity} {product_name}(s) to your cart."
                    else:
                        return f"Error: {cart_response.get('response_message', 'Failed to add item to cart.')}"
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
                    if cart_response.get('response_message') == 'Item added successfully':
                        return f"Successfully added {self.current_service_product['product_name']} to your cart."
                    else:
                        return f"Error: {cart_response.get('response_message', 'Failed to add service to cart.')}"
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
        print("You can:")
        print("- Check your pincode for available products")
        print("- View your order status by typing 'show order status' or 'my orders'")
        
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
            print("Type 'show order status' or 'my orders' to check your orders")
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
