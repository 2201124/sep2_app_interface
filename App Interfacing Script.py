import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageDraw, ImageFont
import os
import subprocess
import time
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter

# Load the Firebase credentials from a JSON file
# i left this out from github because random people might access this
cred = credentials.Certificate(r"C:\Users\nicho\Desktop\SEP2 App interface\sep2-39da7-firebase-adminsdk-lqp4n-0258736750.json")
firebase_admin.initialize_app(cred)

# Initialize Firestore client so we can access the database
db = firestore.client()



# Execute an ADB (Android Debug Bridge) command and return the output
# Used extensively because we are sending commands to the android phone
def adb_command(command):
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout

# Perform a tap action on the phone screen at (x, y) coordinates
def tap_screen(x, y):
    adb_command(f"adb shell input tap {x} {y}")

# Perform a long press action on the phone screen at (x, y) coordinates for a specified duration
def long_press(x, y, duration):
    # There's 2 x and y because its the start and end position of the long press
    adb_command(f"adb shell input swipe {x} {y} {x} {y} {duration}")

#####################  Android Macros Functions ##########################################



# Import photos using a sequence of tap and long press actions
def import_photos_macro():
    actions = [
        ("tap", (420, 1800)),     # Tap "Album" button
        ("tap", (525, 460)),      # Tap "Camera"
        ("long_press", (145, 850, 2000)), # Long press on the first photo
        ("tap", (983, 175)),      # Tap "Share"
        ("tap", (640, 2150)),     # Tap "Bluetooth"
        ("tap", (540, 940)),      # Tap device name
        ("tap", (370, 1760)),     # Tap "Send"
        ("tap", (541, 2330))      # Tap "OK"
    ]

    for action in actions:
        if action[0] == "tap":
            x, y = action[1]
            tap_screen(x, y)
        elif action[0] == "long_press":
            x, y, duration = action[1]
            long_press(x, y, duration)
        time.sleep(2)  # Wait 2 seconds between actions

# Perform the label printing macro with photo deletion and database update
def printlab_macro(staff_id, ward_number):
    coordinates = [(550, 2200), (900, 190), (525, 1000), (150, 460), (940, 2200), (536, 2100)]
    reset_app = [(541, 2330), (300, 2330), (595, 2100)]
    num_photos = get_number_of_photos()  # Get the number of photos
    update_status(f"Number of photos: {num_photos}")

    for _ in range(num_photos):
        for x, y in coordinates:
            tap_screen(x, y)
            time.sleep(2)  # Wait 2 seconds between taps
        update_status("Please Print the image now!!!!")
        time.sleep(30)  # Wait for printing
        update_status("Waiting for 5 seconds then deleting the newest photo")
        update_database(staff_id, ward_number)  # Update Firestore DB
        for x, y in reset_app:
            tap_screen(x, y)
            time.sleep(1)  # Wait 1 second between resets
        time.sleep(3)
        delete_oldest_photo()  # Delete the newest photo
        time.sleep(3)



##################### Image Generation Functions ##########################################


# Generate an image with patient information and save it
def generate_image(ward_number, patient_name, bed_number, cuisine, restrictions, image_number):
    update_status(f"Generating image for {patient_name}, Bed {bed_number}")
    cell_width = 200
    cell_height = 50

    # Calculate image dimensions
    img_width = cell_width * 2
    img_height = cell_height * 4

    # Create an image with a white background
    img = Image.new('RGB', (img_width, img_height), color='white')
    draw = ImageDraw.Draw(img)

    # Define fonts and sizes
    try:
        header_font = ImageFont.truetype("arialbd.ttf", 24)  # Use Arial Bold font
        text_font = ImageFont.truetype("arial.ttf", 20)
    except IOError:
        header_font = ImageFont.load_default()
        text_font = ImageFont.load_default()

    # Define the text to be written
    headers = ["Patient Name", "Bed Number", "Cuisine Type", "Restrictions"]
    values = [patient_name, str(bed_number), cuisine, restrictions]

    # Draw gridlines
    for i in range(1, 4):
        draw.line([(0, i * cell_height), (img_width, i * cell_height)], fill='black')
    for j in range(1, 2):
        draw.line([(j * cell_width, 0), (j * cell_width, img_height)], fill='black')

    # Add text to the grid
    for i in range(4):
        draw.text((10, i * cell_height + 10), headers[i], font=header_font, fill='black')
        draw.text((cell_width + 10, i * cell_height + 10), values[i], font=text_font, fill='black')

    image_path = f'{ward_number}_{bed_number}_{image_number:02d}.png'
    img.save(image_path)  # Save the image
    update_status(f"Image saved as {image_path}")
    return image_path

# Send the generated image to the phone via ADB
def send_image(image_path):
    update_status(f"Sending image {image_path} to phone")
    adb_command(f"adb push {image_path} /storage/emulated/0/DCIM/Screenshots")

# Retrieve patient data from Firestore and generate images
def retrieve_and_generate_images(ward_number, staff_id):
    update_status(f"Retrieving data for ward number {ward_number}")
    
    # Read from the database
    ward_ref = db.collection('Wards').document(ward_number).collection('Bed_Number')
    
    # Query for Bed_Number in ascending order
    query = ward_ref.order_by('Bed_Number', direction=firestore.Query.ASCENDING)
    patients = query.stream()
    counter = 0
    for patient in patients:
        data = patient.to_dict()
        image_path = generate_image(data['Ward_Number'], data['Patient_Name'], data['Bed_Number'], data['Cuisine_Type'], data['Restrictions'], counter)
        counter += 1
        send_image(image_path)
        time.sleep(1)
        os.remove(image_path)  # Remove the image after sending it to the phone

    import_photos_macro()  # Import photos to android phone
    printlab_macro(staff_id, ward_number)  # Print labels

# Delete the oldest photo from the phone's camera directory
def delete_oldest_photo():

    # List all of the folder contents in the camera
    command = 'adb shell ls -t -r /storage/emulated/0/DCIM/Camera'
    result = adb_command(command)
    file_list = result.strip().split('\n')

    if file_list:
        oldest_file = file_list[0].strip()
        delete_command = f'adb shell rm "/storage/emulated/0/DCIM/Camera/{oldest_file}"'
        delete_result = adb_command(delete_command)
        update_status(f"Deleting oldest photo '{oldest_file}'")
    else:
        update_status("No photos found in directory")

# Get the number of photos in the phone's camera directory
def get_number_of_photos():
    result = adb_command("adb shell ls /storage/emulated/0/DCIM/Camera")
    if result.strip() == '':
        update_status("Error: No output from adb command.")
        return 0
    file_list = result.strip().split('\n')
    num_photos = len(file_list)
    return num_photos

# Get the list of photos in the phone's camera directory
def get_photos():
    result = adb_command("adb shell ls /storage/emulated/0/DCIM/Camera")
    if result.strip() == '':
        update_status("Error: No output from adb command.")
        return []
    file_list = result.strip().split('\n')
    return file_list



##################### Database Function ##########################################

# Update the Firestore database with the staff ID for the given ward number
# This is to provide traceability of the food preparation quality incase there's discrepancies in food quality

def update_database(staff_id, ward_number):
    
    # So the 3 lines above is scanning the photo names and split it into ward and bed numbers
    # Because we're trying to update the database of the specific bed number
    # The "found" flag is to mitigate the issue where it will update the entire database with the staff's id
    # instead of doing it according to the bed number
    
    photos = get_photos()
    found = False
    for photo in photos:
        parts = photo.split('_')
        if len(parts) == 3:
            ward, bed, _ = parts           
            if ward == str(ward_number) and not found:
                patient_doc_ref = db.collection('Wards').document(str(ward_number)).collection('Bed_Number').document(f"{bed}")
                patient_snapshot = patient_doc_ref.get()
                if patient_snapshot.exists:
                    current_prepared_by = patient_snapshot.get('Prepared_By')
                    if current_prepared_by != staff_id:
                        patient_doc_ref.update({'Prepared_By': staff_id})
                        update_status(f"Updated Firebase DB with staff_id: {staff_id} for ward: {ward} bed: {bed}")
                        found = True
                else:
                    update_status(f"Document with Bed_Number {bed} does not exist.")
    if not found:
        update_status(f"No document found in ward {ward_number} to update.")




# Update the status message on the Tkinter GUI
def update_status(message):
    status_label.config(text=message)
    root.update_idletasks()

# Handle the submission of the form
def on_submit():
    ward_number = entry_ward.get()
    staff_id = entry_staff.get()
    if not ward_number:
        messagebox.showerror("Input Error", "Ward Number is required")
        return
    if not staff_id:
        messagebox.showerror("Input Error", "Staff ID is required")
        return
    update_status("Starting process...")
    retrieve_and_generate_images(ward_number, staff_id)
    update_status("Process completed.")

# Set up the Tkinter GUI
root = tk.Tk()
root.title("Patient Information Form")
root.geometry("400x200")  # Set fixed size for the window

tk.Label(root, text="Ward Number").grid(row=0, column=0)
entry_ward = tk.Entry(root)
entry_ward.grid(row=0, column=1)

tk.Label(root, text="Staff ID").grid(row=1, column=0)
entry_staff = tk.Entry(root)
entry_staff.grid(row=1, column=1)

submit_button = tk.Button(root, text="Submit", command=on_submit)
submit_button.grid(row=2, column=0, columnspan=2)

status_label = tk.Label(root, text="", wraplength=350)  # Wrap text if it gets too long
status_label.grid(row=3, column=0, columnspan=2)

root.mainloop()
