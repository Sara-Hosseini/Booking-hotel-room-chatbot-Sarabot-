import re
import dateparser
from datetime import datetime, timedelta
import csv
import random
import time
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  
BOOKINGS_CSV = os.path.join(BASE_DIR, "data", "bookings.csv")


# Configuration
HOTEL_INFO = {
    "name": "Hotel Sara",
    "address": "123 Alexanderplatz, Berlin, Germany",
    "phone": "+49 123 456 789",
    "email": "contact@hotelsara.com"
}

RESPONSES = {
    "greeting": "Hello! Welcome to Sara Hotel. What can I do for you today?",
    "booking": "Great! Let's start! first of all we need your full name for the reservation.",
    "price": "Room prices start at 79€/night for a Single Room, 109€ for King Room, 109€ for Two Bed Room, and 159€ for Family Suite.",
    "goodbye": "Thank you for visiting! Hope to see you again.",
    "about": "I’m SaraBot, your friendly hotel assistant here to help with reservings and more!",
    "unknown": "I’m not sure I understood that. Could you reword or ask about reservings, prices, or something related?"
}

ROOM_OPTIONS = {
    "Single Room": {"price": 79, "description": "1 bed, ideal for solo travelers", "max_guests": 1},
    "King Room": {"price": 109, "description": "1 large king-size bed, ideal for 2 adults", "max_guests": 2},
    "Two Bed Room": {"price": 109, "description": "2 separate beds, great for 2 guests or adult with kid", "max_guests": 2},
    "Family Suite": {"price": 159, "description": "Spacious, multiple beds, perfect for families", "max_guests": 6}
}

ROOM_INVENTORY = {
    "Single Room": 10,
    "King Room": 7,
    "Two Bed Room": 8,
    "Family Suite": 5
}

DATE_FORMATS = ["%Y.%m.%d", "%Y-%m-%d"]

def slow_print(text, delay=0.02):
    """Print text with a typing effect."""
    for char in text:
        print(char, end='', flush=True)
        time.sleep(delay)
    print()

def get_purpose(user_input):
    """Determine the user's intent based on input."""
    user_input = user_input.lower().strip()
    if re.search(r"\b(hi|hello|hey)\b", user_input):
        return "greeting"
    if re.search(r"\b(book|reserve|room)\b", user_input):
        return "booking"
    if re.search(r"\b(price|cost|how much)\b", user_input):
        return "price"
    if re.search(r"\bgoodbye\b", user_input) or re.search(r"\bbye\b", user_input) or re.search(r"\bsee you\b", user_input):
        return "goodbye"
    if re.search(r"\b(name|who are you)\b", user_input):
        return "about"
    return "unknown"

def parser_date(user_input):
    """parser date and number of nights from user input."""
    user_input = user_input.lower().strip()
    today = datetime.today()
    start_date = None
    nights = None

    if "day after tomorrow" in user_input:
        start_date = today + timedelta(days=2)
    elif "tomorrow" in user_input:
        start_date = today + timedelta(days=1)
    elif "today" in user_input:
        start_date = today
    else:
        for fmt in DATE_FORMATS:
            try:
                start_date = datetime.strptime(user_input, fmt)
                break
            except ValueError:
                pass
        if not start_date:
            start_date = dateparser.parse(user_input, languages=['en'])

    if start_date:
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        today_normalized = today.replace(hour=0, minute=0, second=0, microsecond=0)

        if start_date.date() < today_normalized.date():
            return None, None, None, f"The date {user_input} is not valid. Please enter a valid date (e.g., '2025-07-16' or 'tomorrow')."
        if start_date > today_normalized + timedelta(days=365*2):
            return None, None, None, "Booking can be done up to two years in advance. Please enter an earlier date."

    match = re.search(r"for (\d+) nights?|(\d+) nights?", user_input)
    if match:
        nights = int(match.group(1) or match.group(2))

    end_date = start_date + timedelta(days=nights) if start_date and nights else None
    return (
        start_date.strftime("%Y-%m-%d") if start_date else None,
        end_date.strftime("%Y-%m-%d") if end_date else None,
        nights,
        None
    )

def parser_guests(guest_info):
    """parser information about guests (adults, children, ages)."""
    guest_info = guest_info.strip().lower()
    adults, children, children_ages = 0, 0, []

    adults_match = re.search(r'(\d+)\s*adults?', guest_info)
    children_match = re.search(r'(\d+)\s*children?', guest_info)
    ages_match = re.findall(r'ages?\s*([\d,\s]+)', guest_info)

    if adults_match and children_match:
        adults = int(adults_match.group(1))
        children = int(children_match.group(1))
        if children > 0 and ages_match:
            children_ages = [int(age.strip()) for age in ages_match[0].split(',') if age.strip().isdigit()]
            if len(children_ages) != children:
                return 0, 0, [], "The number of children and ages don't match."
    elif re.match(r'^(\d+),\s*(\d+)(,\s*\d+)*$', guest_info):
        parts = [int(p.strip()) for p in guest_info.split(',') if p.strip().isdigit()]
        if len(parts) >= 2:
            adults, children = parts[0], parts[1]
            children_ages = parts[2:] if len(parts) > 2 else []
            if children > 0 and len(children_ages) != children:
                return 0, 0, [], "The number of children and ages didn't match."
        else:
            return 0, 0, [], "Invalid format. Use '2 adults, 1 child, ages 5' or '2,1,5'."
    elif adults_match:
        adults = int(adults_match.group(1))
    else:
        return 0, 0, [], "Invalid format. Please specify at least the number of adults. Use '2 adults' or '2,0' or '2 adults, 1 child, ages 5'."

    return adults, children, children_ages, None

def parser_rooms(room_input, total_guests, start_date, end_date):
    """parser multiple room selections and quantities, checking availability."""
    room_input = room_input.strip().lower()
    if not room_input or room_input in ['cancel', 'exit']:
        return {}, 0, "cancel"
    
    selected_rooms = {}
    total_capacity = 0

    parts = [part.strip() for part in room_input.split(',')]
    for part in parts:
        match = re.match(r'(\d+)\s*(.+)', part)
        if not match:
            return {}, 0, f"Invalid format in '{part}'. Use '1 King Room' or '1 King Room, 1 Two Bed Room'."
        
        quantity = int(match.group(1))
        room_name = match.group(2).strip()
        
        matched_room_name = None
        for r_key in ROOM_OPTIONS:
            if room_name == r_key.lower() or room_name.replace("roo", "room") == r_key.lower():
                matched_room_name = r_key
                break
        
        if not matched_room_name:
            return {}, 0, f"Unknown room type in '{part}'. Did you mean 'King Room' or 'Two Bed Room'? Available: {', '.join(ROOM_OPTIONS.keys())}."
        
        selected_rooms[matched_room_name] = selected_rooms.get(matched_room_name, 0) + quantity
        total_capacity += ROOM_OPTIONS[matched_room_name]["max_guests"] * quantity

    if len(selected_rooms) < 1:
        return {}, 0, "Please select at least 1 room type. For example: '1 Family Suite' or '1 King Room, 1 Two Bed Room'."
    
    if total_capacity < total_guests:
        return {}, 0, f"The selected rooms can accommodate {total_capacity} guests, but you have {total_guests} guests. Try adding more rooms or choosing rooms with higher capacity."

    for room_type, quantity in selected_rooms.items():
        if not check_availability(room_type, quantity, start_date, end_date):
            return {}, 0, f"Sorry, {quantity} {room_type}(s) not available for {start_date} to {end_date}. Please try different rooms or dates."

    return selected_rooms, total_capacity, None

def check_availability(room_type, quantity, start_date, end_date):
    """Check if the requested number of rooms is available for the given dates."""
    try:
        total_rooms = ROOM_INVENTORY[room_type]
        booked_rooms = 0
        file_path = BOOKINGS_CSV


        try:
            with open(file_path, mode="r", newline="", encoding="utf-8") as file:
                reader = csv.reader(file)
                first_row = next(reader, None)
                if first_row and "Name" in first_row[0]:
                    pass  # Header found, no action needed
                else:
                    file.seek(0) if first_row else None

                for row in reader:
                    if len(row) < 7:
                        continue
                    
                    booking_start = row[2]
                    booking_end = row[3]
                    rooms_str = row[6]

                    booked_room_details = {}
                    for room_entry in rooms_str.split(";"):
                        room_entry = room_entry.strip()
                        room_match = re.match(r'(\d+)\s*(.+)', room_entry)
                        if room_match:
                            booked_qty = int(room_match.group(1))
                            booked_room = room_match.group(2).strip()
                            booked_room_details[booked_room] = booked_room_details.get(booked_room, 0) + booked_qty

                    if room_type in booked_room_details:
                        try:
                            booking_start_date = datetime.strptime(booking_start, "%Y-%m-%d")
                            booking_end_date = datetime.strptime(booking_end, "%Y-%m-%d")
                            requested_start = datetime.strptime(start_date, "%Y-%m-%d")
                            requested_end = datetime.strptime(end_date, "%Y-%m-%d")

                            if not (requested_end <= booking_start_date or requested_start >= booking_end_date):
                                booked_rooms += booked_room_details[room_type]
                        except ValueError:
                            continue

            return (booked_rooms + quantity) <= total_rooms
        except FileNotFoundError:
            return quantity <= total_rooms
    except Exception:
        return False

def collect_payment_info(payment_method):
    """Collect and validate payment information based on the payment method."""
    if payment_method == "cash":
        return {"method": "cash", "details": "Payment due at check-in"}, None
    
    if payment_method == "credit card":
        while True:
            card_number = input("SaraBot: Please enter your 16-digit credit card number (no spaces):\nYou: ").strip()
            if card_number.lower() in ['cancel', 'exit']:
                return None, "cancel"
            if not (card_number.isdigit() and len(card_number) == 16):
                print("SaraBot: Invalid card number. Please enter a 16-digit number.")
                continue
            break

        while True:
            expiry = input("SaraBot: Please enter card expiration date (MM/YY):\nYou: ").strip()
            if expiry.lower() in ['cancel', 'exit']:
                return None, "cancel"
            if not re.match(r'^(0[1-9]|1[0-2])/\d{2}$', expiry):
                print("SaraBot: Invalid expiration date. Please use MM/YY format (e.g., 12/25).")
                continue
            month, year = map(int, expiry.split('/'))
            current_year_full = datetime.now().year
            current_month = datetime.now().month
            
            if year < 100:
                year_full = 2000 + year if year >= (current_year_full % 100) else 2100 + year
            else:
                year_full = year

            if (year_full < current_year_full) or \
               (year_full == current_year_full and month < current_month):
                print("SaraBot: Expiration date is in the past. Please try again.")
                continue
            break

        while True:
            cvv = input("SaraBot: Please enter your 3- or 4-digit CVV:\nYou: ").strip()
            if cvv.lower() in ['cancel', 'exit']:
                return None, "cancel"
            if not (cvv.isdigit() and 3 <= len(cvv) <= 4):
                print("SaraBot: Invalid CVV. Please enter a 3- or 4-digit number.")
                continue
            break

        return {"method": "credit card", "card_number": card_number[-4:], "expiry": expiry, "cvv": "XXX"}, None

    if payment_method == "paypal":
        while True:
            email = input("SaraBot: Please enter your PayPal email address:\nYou: ").strip()
            if email.lower() in ['cancel', 'exit']:
                return None, "cancel"
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                print("SaraBot: Invalid email address. Please enter a valid PayPal email.")
                continue
            break

        return {"method": "paypal", "email": email}, None

    return None, "Invalid payment method."

def collect_special_requirements():
    """Collect special requirements (shuttle, disability, other)."""
    special_requirements = {}
    shuttle_cost = 0

    while True:
        shuttle = input("SaraBot: Do you need an airport shuttle for 60€ (up to 4 guests)? (yes/no):\nYou: ").strip().lower()
        if shuttle in ['cancel', 'exit']:
            return None, None, "cancel"
        if shuttle in ['yes', 'y', 'no', 'n']:
            special_requirements["shuttle"] = "Yes" if shuttle in ['yes', 'y'] else "No"
            shuttle_cost = 60 if shuttle in ['yes', 'y'] else 0
            break
        print("SaraBot: Please answer 'yes' or 'no'.")

    while True:
        disability = input("SaraBot: Do you require disability accommodations? (yes/no):\nYou: ").strip().lower()
        if disability in ['cancel', 'exit']:
            return None, None, "cancel"
        if disability in ['yes', 'y']:
            special_requirements["disability"] = "Yes"
            print("SaraBot: We will provide a disability-friendly room with accessible features.")
            break
        if disability in ['no', 'n']:
            special_requirements["disability"] = "No"
            break
        print("SaraBot: Please answer 'yes' or 'no'.")

    while True:
        other = input("SaraBot: Any other special requests? (yes/no):\nYou: ").strip().lower()
        if other in ['cancel', 'exit']:
            return None, None, "cancel"
        if other in ['no', 'n', 'none']:
            special_requirements["other"] = "None"
            break
        if other in ['yes', 'y']:
            while True:
                specific_requests = input("SaraBot: Please enter what special requests you have (e.g., extra pillows, late checkout):\nYou: ").strip()
                if specific_requests.lower() in ['cancel', 'exit']:
                    return None, None, "cancel"
                if specific_requests.lower() == 'none':
                    special_requirements["other"] = "None"
                    break
                if specific_requests:
                    special_requirements["other"] = specific_requests.replace(",", "").replace(";", "")
                    print(f"SaraBot: Thank you, we have noted your special requests: {special_requirements['other']}.")
                    break
                print("SaraBot: Please specify your requests or type 'none'.")
            break
        print("SaraBot: Please answer 'yes' or 'no'.")

    return special_requirements, shuttle_cost, None

def save_booking(name, phone, start, end, nights, guests, rooms, checkin, payment_info, special_requirements):
    """Save booking details to CSV, including multiple rooms, payment info, and special requirements."""
    try:
        booking_ref = str(random.randint(100000, 999999))
        file_path = BOOKINGS_CSV

        # Ensure directory exists
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        # Sanitize inputs to prevent CSV issues
        name = name.replace(",", "").replace(";", "").encode("utf-8", errors="ignore").decode("utf-8")
        phone = phone.replace(",", "").replace(";", "").encode("utf-8", errors="ignore").decode("utf-8")
        special_requirements["other"] = special_requirements["other"].replace(",", "").replace(";", "").encode("utf-8", errors="ignore").decode("utf-8")

        # Check if file exists and is empty
        file_exists = os.path.exists(file_path)
        file_is_empty = file_exists and os.path.getsize(file_path) == 0

        with open(file_path, mode="a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file, quoting=csv.QUOTE_MINIMAL)
            if file_is_empty:
                # Write the title as a comment
                writer.writerow(["# Hotel Sara Booking Records"])
                writer.writerow(["Name", "Phone", "Check-in Date", "Check-out Date", "Nights", "Guests", "Rooms", "Confirmation Date", "Payment Info", "Special Requirements", "Booking Reference"])

            rooms_str = "; ".join([f"{qty} {room}" for room, qty in rooms.items()])
            payment_str = (f"{payment_info['method']}: {payment_info.get('card_number', '')}, "
                           f"Expiry: {payment_info.get('expiry', '')}, CVV: {payment_info.get('cvv', '')}"
                           if payment_info['method'] == "credit card" else
                           f"{payment_info['method']}: {payment_info.get('email', '')}"
                           if payment_info['method'] == "paypal" else
                           payment_info['details'])
            special_str = (f"Shuttle: {special_requirements['shuttle']}, "
                           f"Disability: {special_requirements['disability']}, "
                           f"Other: {special_requirements['other']}")
            row = [name, phone, start, end, nights, guests, rooms_str, checkin, payment_str, special_str, booking_ref]
            writer.writerow(row)

        return True, booking_ref
    except PermissionError as e:
        print(f"SaraBot: Failed to save booking due to permission error: {str(e)}. Please check directory permissions for {file_path}.")
        return False, None
    except UnicodeEncodeError as e:
        print(f"SaraBot: Failed to save booking due to encoding error: {str(e)}. Please avoid special characters in input.")
        return False, None
    except FileNotFoundError as e:
        print(f"SaraBot: Failed to save booking: Directory or file path {file_path} not found. Please ensure the directory exists.")
        return False, None
    except Exception as e:
        print(f"SaraBot: Failed to save booking due to unexpected error: {str(e)}. Please try again or contact support.")
        return False, None

def generate_booking_summary(booking_data, is_final=False):
    """Generates and prints a formatted booking summary with a slow appearance effect."""
    rooms = booking_data['rooms']
    room_details = "\n".join([f"  - {qty} {room} @ {ROOM_OPTIONS[room]['price']}€/night x {booking_data['nights']} nights = {qty * ROOM_OPTIONS[room]['price'] * booking_data['nights']}€" for room, qty in rooms.items()])
    
    payment_details = "N/A"
    if booking_data['payment_info']:
        if booking_data['payment_info']['method'] == "credit card":
            payment_details = f"Credit Card (Card ending: {booking_data['payment_info'].get('card_number', '')})"
        elif booking_data['payment_info']['method'] == "paypal":
            payment_details = f"PayPal (Email: {booking_data['payment_info'].get('email', '')})"
        else:
            payment_details = f"Cash ({booking_data['payment_info'].get('details', '')})"
    
    summary_lines = []
    summary_lines.append(f"\nSaraBot: {'📋 Final Reservation Summary' if is_final else '✅ Booking Summary'}:")
    summary_lines.append("--- Guest Details ---")
    summary_lines.append(f"- Guest Name: {booking_data['name']}")
    if is_final:
        summary_lines.append(f"- Phone: {booking_data['phone']}")
    summary_lines.append(f"- Booking Reference: {booking_data['booking_ref'] if booking_data['booking_ref'] != 'TBD' else 'Pending'}")
    
    summary_lines.append("\n--- Booking Details ---")
    summary_lines.append(f"- Check-in: {booking_data['start']}")
    summary_lines.append(f"- Check-out: {booking_data['end']}")
    summary_lines.append(f"- Duration: {booking_data['nights']} nights")
    summary_lines.append(f"- Guests: {booking_data['guests']}")
    summary_lines.append("- Rooms:")
    summary_lines.extend(room_details.split('\n'))
    
    summary_lines.append("\n--- Special Requirements ---")
    summary_lines.append(f"- Airport Shuttle: {booking_data['special_requirements']['shuttle']} ({'60€' if booking_data['special_requirements']['shuttle'] == 'Yes' else 'Not included'})")
    summary_lines.append(f"- Disability Accommodations: {booking_data['special_requirements']['disability']}")
    summary_lines.append(f"- Other Requests: {booking_data['special_requirements']['other']}")
    
    summary_lines.append("\n--- Cost Breakdown ---")
    summary_lines.append(f"- Room Cost: {booking_data['room_total']}€")
    summary_lines.append(f"- Breakfast: {'Included (' + str(booking_data['breakfast_cost']) + '€)' if booking_data['breakfast'] == 'Included' else 'Not included'}")
    summary_lines.append(f"- Airport Shuttle: {booking_data['shuttle_cost']}€")
    summary_lines.append(f"- Total (excluding taxes): {booking_data['total_price']}€")
    tax = round(booking_data['total_price'] * 0.10, 2)
    summary_lines.append(f"- Taxes (10%): {tax}€")
    summary_lines.append(f"-  Grand Total: {booking_data['total_price'] + tax}€")
    summary_lines.append("\n--- Cancellation Policy ---")
    summary_lines.append("- Free cancellation up to 48 hours before arrival. Contact us to modify or cancel your booking.\n")
    
    if is_final:
        summary_lines.append("\n--- Confirmation ---")
        summary_lines.append(f"- Booking Confirmed: {booking_data['checkin']}")
        summary_lines.append(f"- Payment: {payment_details}")
    
    for line in summary_lines:
        slow_print(line)
        time.sleep(0.05)

def handle_booking():
    """Handle the booking parser with multiple room types and special requirements."""
    booking_data = {}

    # Step 1: Display booking response
    slow_print("SaraBot: " + RESPONSES["booking"])

    # Step 2: Name
    name = input("SaraBot: Your full name?\nYou: ").strip()
    if name.lower() in ['cancel', 'exit']:
        print("SaraBot: Booking canceled. Let me know how I can assist you further!")
        return None

    # Step 3: Phone Number
    while True:
        phone = input("SaraBot: Your phone number?\nYou: ").strip()
        if phone.lower() in ['cancel', 'exit']:
            print("SaraBot: Booking canceled. Let me know how I can assist you further!")
            return None
        if not re.match(r'^\+?[\d\s\-\(\)]{7,20}$', phone):
            print("SaraBot: Invalid phone number format. Please enter a valid phone number (e.g., +49 123 456 789).")
            continue
        break

    # Step 4: Dates
    print("SaraBot: What dates would you like to book? (e.g., 'tomorrow' or '2025-07-16')")
    while True:
        date_input = input("You: ").strip()
        if date_input.lower() in ['cancel', 'exit']:
            print("SaraBot: Booking canceled. Let me know how I can assist you further!")
            return None
        start, end, nights, error = parser_date(date_input)
        if error:
            print(f"SaraBot: {error}")
            continue
        if not start:
            print("SaraBot: I couldn't understand that date. Please try again (e.g., '2025-07-16' or 'tomorrow').")
            continue

        if not nights:
            try:
                nights_input = input("SaraBot: How many nights would you like to stay?\nYou: ").strip()
                if nights_input.lower() in ['cancel', 'exit']:
                    print("SaraBot: Booking canceled. Let me know how I can assist you further!")
                    return None
                nights = int(nights_input)
            except ValueError:
                nights = 1
                print("SaraBot: Invalid input. Assuming 1 night.")
            end = (datetime.strptime(start, "%Y-%m-%d") + timedelta(days=nights)).strftime("%Y-%m-%d")
            
        print(f"SaraBot: Booking from {start} to {end} for {nights} nights.")
        break

    # Step 5: Number of Guests
    while True:
        guest_info = input("SaraBot: Please enter number of adults, children, and their ages (e.g., '2 adults, 1 child, ages 5' or '2,1,5'):\nYou: ").strip()
        if guest_info.lower() in ['cancel', 'exit']:
            print("SaraBot: Booking canceled. Let me know how I can assist you further!")
            return None
        adults, children, children_ages, error = parser_guests(guest_info)
        if error:
            print(f"SaraBot: {error}")
            continue
        if adults < 1:
            print("SaraBot: At least one adult is required.")
            continue
        break

    total_guests = adults + children
    print(f"SaraBot: Got it — Adults: {adults}, Children: {children}, Ages: {', '.join(map(str, children_ages)) if children_ages else 'N/A'}")

    # Step 6: Number of Rooms and Their Types
    print(f"SaraBot: Based on {total_guests} guests, available room options:")
    for room, details in ROOM_OPTIONS.items():
        print(f"- {room}: {details['price']}€/night — {details['description']}, ensuite bathroom, TV, Wi-Fi (up to {details['max_guests']} guests)")

    selected_rooms = {}
    while not selected_rooms:
        room_input = input("SaraBot: Please select one or more room types and quantities (e.g., '1 Family Suite' or '1 King Room, 1 Two Bed Room') or type 'cancel' to exit:\nYou: ").strip()
        selected_rooms, total_capacity, error = parser_rooms(room_input, total_guests, start, end)
        if error == "cancel":
            print("SaraBot: Booking canceled. Let me know how I can assist you further!")
            return None
        if error:
            print(f"SaraBot: {error}")
            selected_rooms = {}
            continue
        break

    # Step 7: Breakfast Preference
    breakfast_input = input("SaraBot: Include breakfast for 15€ per person per night? (yes/no)\nYou: ").strip().lower()
    if breakfast_input in ['cancel', 'exit']:
        print("SaraBot: Booking canceled. Let me know how I can assist you further!")
        return None
    include_breakfast = breakfast_input in ['yes', 'y']
    breakfast_cost = 15 * total_guests * nights if include_breakfast else 0

    # Step 8: Special Requests
    special_requirements, shuttle_cost, error = collect_special_requirements()
    if error == "cancel":
        print("SaraBot: Booking canceled. Let me know how I can assist you further!")
        return None

    # Step 9: Payment Method
    payment_method = input("SaraBot: Payment method? (credit card, PayPal, cash)\nYou: ").strip().lower()
    if payment_method in ['cancel', 'exit']:
        print("SaraBot: Booking canceled. Let me know how I can assist you further!")
        return None
    if payment_method not in ["credit card", "paypal", "cash"]:
        print("SaraBot: Invalid payment method. Please choose from 'credit card', 'paypal', or 'cash'.")
        return None

    payment_info, error = collect_payment_info(payment_method)
    if error == "cancel":
        print("SaraBot: Booking canceled. Let me know how I can assist you further!")
        return None
    if error:
        print(f"SaraBot: {error} Please try again.")
        return None

    # Calculate costs
    room_total = sum(ROOM_OPTIONS[room]["price"] * qty * nights for room, qty in selected_rooms.items())
    total_price = room_total + breakfast_cost + shuttle_cost

    # Store booking data
    booking_data = {
        'name': name,
        'phone': phone,
        'start': start,
        'end': end,
        'nights': nights,
        'guests': f"{adults} adults, {children} children ({', '.join(map(str, children_ages)) if children_ages else 'N/A'})",
        'rooms': selected_rooms,
        'checkin': '',
        'special_requirements': special_requirements,
        'breakfast': 'Included' if include_breakfast else 'Not included',
        'payment_info': payment_info,
        'room_total': room_total,
        'breakfast_cost': breakfast_cost,
        'shuttle_cost': shuttle_cost,
        'total_price': total_price,
        'booking_ref': 'TBD'
    }

    # Step 10: Booking Confirmation
    generate_booking_summary(booking_data)

    confirm_input = input("SaraBot: Confirm booking? (yes/no)\nYou: ").strip().lower()
    if confirm_input in ['cancel', 'exit']:
        print("SaraBot: Booking canceled. Let me know how I can assist you further!")
        return None
    if confirm_input in ['yes', 'y']:
        checkin = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        booking_data['checkin'] = checkin
        print("SaraBot: About to save booking...")
        success, booking_ref = save_booking(name, phone, start, end, nights, booking_data['guests'], selected_rooms, checkin, payment_info, special_requirements)
        if success:
            booking_data['booking_ref'] = booking_ref
            slow_print(f"SaraBot:  Thank you, {name}! Your booking is confirmed. Booking Reference: {booking_ref}")
            slow_print("SaraBot: Hotel Information:")
            slow_print(f"- Name: {HOTEL_INFO['name']}")
            slow_print(f"- Address: {HOTEL_INFO['address']}")
            slow_print(f"- Phone: {HOTEL_INFO['phone']}")
            slow_print(f"- Email: {HOTEL_INFO['email']}")
            return booking_data
        else:
            return None
    else:
        print("SaraBot: Booking canceled. Let me know how I can assist you further!")
        return None

def main():
    last_booking = None
    slow_print("SaraBot: Hello! Welcome to Sara Hotel's chatbot. What can I do for you today?")
    while True:
        user_input = input("You: ").strip()
        if not user_input and last_booking:
            print("SaraBot: Would you like to view your last booking summary, make another booking, or exit? (view/book/exit)")
            user_input = input("You: ").strip().lower()
            if user_input == "view":
                generate_booking_summary(last_booking, is_final=True)
                print("SaraBot: What would you like to do next? (e.g., 'book', 'exit')")
                continue
            elif user_input == "book":
                last_booking = handle_booking()
                continue
            elif user_input == "exit":
                slow_print("SaraBot: " + RESPONSES["goodbye"])
                break
            else:
                print("SaraBot: Please choose 'view', 'book', or 'exit'.")
                continue
        elif not user_input:
            print("SaraBot: Please type something to continue.")
            continue

        intent = get_purpose(user_input)
        if intent == "goodbye":
            slow_print("SaraBot: " + RESPONSES["goodbye"])
            break
        elif intent == "booking":
            last_booking = handle_booking()
        else:
            print("SaraBot:", RESPONSES[intent])

if __name__ == "__main__":
    main()
