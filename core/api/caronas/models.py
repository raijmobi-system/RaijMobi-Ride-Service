from django.db import models
from core.models import BaseModel, BaseModelWithSoftDelete, UserClient

class Veiculo(BaseModel):
    usuario = models.ForeignKey(
        UserClient,
        on_delete=models.CASCADE,
        related_name="veiculos"
    )
    modelo = models.CharField(max_length=100)
    cor = models.CharField(max_length=50)
    placa = models.CharField(max_length=10)

    def __str__(self):
        return f"{self.modelo} - {self.placa}"
    
class Carona(BaseModelWithSoftDelete):
    motorista = models.ForeignKey(
        UserClient,
        on_delete=models.CASCADE,
        related_name="caronas_motorista"
    )
    veiculo = models.ForeignKey(
        Veiculo,
        on_delete=models.CASCADE,
        related_name="caronas"

    )
    origem = models.CharField(max_length=255)
    destino = models.CharField(max_length=255)
    data_hora_saida = models.DateTimeField()
    vagas_totais = models.IntegerField()
    status = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.origem} -> {self.destino}"
    

class Reserva(BaseModelWithSoftDelete):
    carona = models.ForeignKey(
        Carona,
        on_delete=models.CASCADE,
        related_name="reservas"
    )
    passageiro = models.ForeignKey(
        UserClient,
        on_delete=models.CASCADE,
        related_name="reservas"
    )
    status = models.CharField(max_length=50)

    def __str__(self):
        return f"Reserva {self.id}"


