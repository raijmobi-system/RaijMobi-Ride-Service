import stripe
from django.conf import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

class StripePaymentService:
    @staticmethod
    def create_payment_sheet_params(amount_cents: int, user: object, reservation_id: str):
        """
        Gera os parâmetros necessários para o Stripe Payment Sheet (Capacitor/Nativo).
        """
        # 1. Cria ou recupera o cliente no Stripe. 
        # DICA: O ideal no futuro é salvar o 'stripe_customer_id' no seu model UserClient 
        # para não precisar criar um novo toda vez. Por hora, faremos a busca por e-mail ou criação:
        customers = stripe.Customer.list(email=user.email).data if hasattr(user, 'email') else []
        
        if customers:
            customer = customers[0]
        else:
            customer = stripe.Customer.create(
                name=user.name if hasattr(user, 'name') else str(user.id),
                email=user.email if hasattr(user, 'email') else None,
                metadata={'user_id': str(user.id)}
            )

        # 2. Cria a chave efêmera de segurança (obrigatória para o PaymentSheet)
        ephemeral_key = stripe.EphemeralKey.create(
            customer=customer.id,
            stripe_version='2023-10-16', # Use uma versão recente da API
        )

        # 3. Cria o PaymentIntent atrelado ao cliente e habilitando PIX e Cartão
        payment_intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency='brl',
            customer=customer.id,
            # 'automatic_payment_methods' é altamente recomendado no Payment Sheet.
            # Ele lê do seu painel do Stripe e exibe Cartão, Apple Pay, Google Pay e PIX automaticamente!
            automatic_payment_methods={'enabled': True}, 
            metadata={
                'user_id': str(user.id),
                'reservation_id': str(reservation_id)
            }
        )

        return {
            'paymentIntent': payment_intent.client_secret,
            'ephemeralKey': ephemeral_key.secret,
            'customer': customer.id,
            'publishableKey': settings.STRIPE_PUBLISHABLE_KEY # Opcional enviar daqui, mas facilita no front
        }

    @staticmethod
    def refund_payment(payment_intent_id: str):
        try:
            return stripe.Refund.create(payment_intent=payment_intent_id)
        except stripe.error.StripeError as e:
            print(f"❌ Erro ao estornar no Stripe: {e}")
            return None