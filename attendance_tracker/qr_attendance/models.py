# qr_attendance/models.py
from django.db import models
import qrcode
from io import BytesIO
import base64

class Attendee(models.Model):
    name = models.CharField(max_length=100)
    job_title = models.CharField(max_length=100)
    qr_code = models.CharField(max_length=100, unique=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def get_qr_code_image(self):
        qr = qrcode.QRCode(version=1, box_size=5, border=2)
        qr.add_data(self.qr_code)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert image to base64
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
        return img_str

class Attendance(models.Model):
    attendee = models.ForeignKey(Attendee, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='Present')