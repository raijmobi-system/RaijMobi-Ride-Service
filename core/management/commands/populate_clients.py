import uuid
from django.core.management.base import BaseCommand
from faker import Faker
from core.models import UserClient 
class Command(BaseCommand):
    help = 'Popula o banco de dados com UserClients falsos para testes.'

    def add_arguments(self, parser):
        # Permite escolher quantos usuários criar (padrão é 10)
        parser.add_argument(
            '--quantidade', 
            type=int, 
            default=10, 
            help='Quantidade de clientes a serem criados'
        )

    def handle(self, *args, **kwargs):
        quantidade = kwargs['quantidade']
        fake = Faker('pt_BR') # Gera dados em Português do Brasil

        self.stdout.write(self.style.WARNING(f'Iniciando criação de {quantidade} clientes...'))

        clientes_criados = 0
        for _ in range(quantidade):
            UserClient.objects.create(
                id=uuid.uuid4(),
                nome=fake.name()
            )
            clientes_criados += 1

        self.stdout.write(self.style.SUCCESS(f'Sucesso! {clientes_criados} clientes foram criados no banco local.'))