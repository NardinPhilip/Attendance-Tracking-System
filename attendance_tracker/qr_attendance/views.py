# qr_attendance/views.py
from django.shortcuts import render, redirect, HttpResponse
from django.http import JsonResponse
import pandas as pd
import qrcode
from PIL import Image, ImageDraw, ImageFont
import uuid
from .models import Attendee, Attendance
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

def upload_excel(request):
    if request.method == 'POST':
        excel_file = request.FILES['excel_file']
        try:
            df = pd.read_excel(excel_file)
            duplicates = []
            for index, row in df.iterrows():
                name = row['Name']
                job_title = row['Job Title']
                if not Attendee.objects.filter(name=name, job_title=job_title).exists():
                    Attendee.objects.create(
                        name=name,
                        job_title=job_title,
                        qr_code=str(uuid.uuid4())
                    )
                else:
                    duplicates.append(f"{name} ({job_title})")
            if duplicates:
                error_msg = "The following entries were skipped as they already exist: " + ", ".join(duplicates)
                return render(request, 'qr_attendance/upload.html', {'error': error_msg})
            return redirect('attendee_list')
        except Exception as e:
            return render(request, 'qr_attendance/upload.html', {'error': str(e)})
    return render(request, 'qr_attendance/upload.html')

# qr_attendance/views.py
from django.http import HttpResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from .models import Attendee
import qrcode
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

def generate_qr_stickers(request):
    attendees = Attendee.objects.all()
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="qr_stickers.pdf"'
    
    c = canvas.Canvas(response, pagesize=letter)
    width, height = letter  # 612.0 x 792.0 points (floats)
    
    # Convert to integers for PIL
    page_width = int(width)   # 612 pixels
    page_height = int(height) # 792 pixels
    
    for attendee in attendees:
        # Generate QR code
        qr = qrcode.QRCode(
            version=None,  # Auto-determine version
            error_correction=qrcode.constants.ERROR_CORRECT_H,  # High error correction
            box_size=15,   # Box size for clarity
            border=4       # Border for padding
        )
        # Use only the UUID or relative path, not the full URL
        qr.add_data(f"/scan/{attendee.qr_code}")  # Relative path
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # Calculate QR code size to leave space for text (above and below)
        qr_width = page_width - 100   # Leave 50 pixels on each side
        qr_height = page_height - 200 # Leave 100 pixels top and bottom for text
        qr_resized = qr_img.resize((qr_width, qr_height))  # e.g., 512x592
        
        # Create full-page image with white background
        full_page = Image.new('RGB', (page_width, page_height), 'white')  # 612x792
        draw = ImageDraw.Draw(full_page)
        
        # Center the QR code vertically and horizontally
        qr_x = (page_width - qr_width) // 2  # e.g., (612 - 512) / 2 = 50
        qr_y = (page_height - qr_height) // 2  # e.g., (792 - 592) / 2 = 100
        full_page.paste(qr_resized, (qr_x, qr_y))
        
        # Load fonts
        try:
            font = ImageFont.truetype("arial.ttf", 40)
            bold_font = ImageFont.truetype("arialbd.ttf", 40)
        except:
            font = ImageFont.load_default()
            bold_font = font
        
        # Add text in reserved areas (above and below QR code)
        welcome_text = "Welcome to ACOC25 IFTAR"
        name_text = f"Name: {attendee.name}"
        
        # Calculate text positions (centered horizontally)
        welcome_bbox = draw.textbbox((0, 0), welcome_text, font=bold_font)
        welcome_width = welcome_bbox[2] - welcome_bbox[0]
        name_bbox = draw.textbbox((0, 0), name_text, font=font)
        name_width = name_bbox[2] - name_bbox[0]
        
        welcome_x = (page_width - welcome_width) // 2  # Center horizontally
        name_x = (page_width - name_width) // 2
        draw.text((welcome_x, 30), welcome_text, font=bold_font, fill="black")  # Above QR
        draw.text((name_x, page_height - 70), name_text, font=font, fill="black")  # Below QR
        
        # Save to BytesIO (no rotation)
        page_buffer = BytesIO()
        full_page.save(page_buffer, format="PNG")
        page_buffer.seek(0)
        
        # Use ImageReader for ReportLab
        page_image = ImageReader(page_buffer)
        
        # Draw to fill the entire page
        c.drawImage(page_image, 0, 0, width=width, height=height, preserveAspectRatio=False)
        c.showPage()  # One page per QR code
    
    c.save()
    return response

# qr_attendance/views.py
from django.http import JsonResponse
from .models import Attendee, Attendance

def scan_qr(request, code):
    # Extract UUID from the code (handles "/scan/<uuid>" or just "<uuid>")
    try:
        # If code is a path like "/scan/<uuid>", extract the UUID
        if code.startswith('/scan/'):
            code = code.split('/scan/')[1].strip('/')  # e.g., "842d0764-dded-4f3d-b7c5-eb1a2a60ddc1"
        
        # Look up attendee by UUID
        attendee = Attendee.objects.get(qr_code=code)
        
        # Check if already scanned
        if Attendance.objects.filter(attendee=attendee).exists():
            return JsonResponse({
                'status': 'already_scanned',
                'message': f'{attendee.name} ({attendee.job_title}) has already attended.'
            })
        else:
            # Record attendance
            Attendance.objects.create(attendee=attendee)
            return JsonResponse({
                'status': 'success',
                'message': f'Successfully recorded attendance for {attendee.name} ({attendee.job_title}).'
            })
    except Attendee.DoesNotExist:
        return JsonResponse({
            'status': 'not_found',
            'message': 'QR code not found or invalid.'
        })
    except Exception as e:
        # Catch unexpected errors (e.g., malformed input)
        return JsonResponse({
            'status': 'error',
            'message': f'Error processing QR code: {str(e)}'
        })

def attendance_list(request):
    attendances = Attendance.objects.all().order_by('-timestamp')
    return render(request, 'qr_attendance/attendance_list.html', {
        'attendances': attendances
    })

def attendee_list(request):
    attendees = Attendee.objects.all()
    for attendee in attendees:
        attendee.qr_code_image = attendee.get_qr_code_image()
    return render(request, 'qr_attendance/attendee_list.html', {
        'attendees': attendees
    })

def scan_page(request):
    attendances = Attendance.objects.all().order_by('-timestamp')
    return render(request, 'qr_attendance/scan.html', {
        'attendances': attendances
    })

def flush_attendees(request):
    if request.method == 'POST':
        Attendee.objects.all().delete()
        return redirect('attendee_list')
    return redirect('attendee_list')

def flush_attendance(request):
    if request.method == 'POST':
        Attendance.objects.all().delete()
        return redirect('attendance_list')
    return redirect('attendance_list')