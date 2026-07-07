from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from core.models import Reservation

class Command(BaseCommand):
    help = 'Cancela reservas pendentes sem pagamento que passaram do limite de 12 horas'

    def handle(self, *args, **kwargs):
        limite_tempo = timezone.now() - timedelta(hours=12)
        
        # Filtra as reservas criadas há mais de 12 horas que continuam como pendentes
        reservas_expiradas = Reservation.objects.filter(
            status='pendente',
            created_at__lt=limite_tempo
        )
        
        count = reservas_expiradas.count()
        
        for reservation in reservas_expiradas:
            reservation.status = 'cancelada'
            reservation.save() # O seu model.py já vai devolver as vagas para a Carona!
            
        self.stdout.write(self.style.SUCCESS(f'{count} reservas expiradas foram canceladas com sucesso.'))