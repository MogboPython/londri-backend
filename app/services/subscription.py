import random
import string
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status

from app.models.subscription import CustomerSubscription, SubscriptionStatus
from app.models.user import User, UserRole
from app.repositories.business_repository import BusinessRepository
from app.repositories.catalog_repository import SubscriptionPlanRepository
from app.repositories.subscription_repository import CustomerSubscriptionRepository
from app.repositories.transaction_repository import TransactionRepository

from .payment import PaymentService


class SubscriptionService:
    def __init__(
            self,
            business_repo: BusinessRepository,
            subscription_repo: CustomerSubscriptionRepository,
            plan_repo: SubscriptionPlanRepository,
            txn_repo: TransactionRepository,
            nomba_payment: PaymentService,
    ) -> None:
        self._business_repo = business_repo
        self._subscription_repo = subscription_repo
        self._plan_repo = plan_repo
        self._txn_repo = txn_repo
        self._nomba_payment = nomba_payment

    async def _resolve_business(self, owner: User) -> uuid.UUID:
        business = await self._business_repo.get_by_owner(owner.id)
        if not business:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No business registered for this account.",
            )
        return business.id

    async def _generate_transaction_reference(self) -> str:
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        while True:
            letters = "".join(random.choices(string.ascii_uppercase, k=3))
            digits = f"{random.randint(0, 999):03d}"
            candidate = f"PAY-{today}-{letters}{digits}"
            if not await self._txn_repo.get_by_reference_id(candidate):
                return candidate

    @staticmethod
    def _to_dict(subscription: CustomerSubscription) -> dict[str, Any]:
        return {
            "id": str(subscription.id),
            "business_id": str(subscription.business_id),
            "customer_id": str(subscription.customer_id),
            "plan_id": str(subscription.plan_id),
            "plan_version": subscription.plan_version,
            "status": subscription.status,
            "current_period_start": subscription.current_period_start,
            "current_period_end": subscription.current_period_end,
            "next_billing_date": subscription.next_billing_date,
            "items_used_in_current_period": subscription.items_used_in_current_period,
            "cancel_at_period_end": subscription.cancel_at_period_end,
            "cancelled_at": subscription.cancelled_at,
            "created_at": subscription.created_at,
            "updated_at": subscription.updated_at,
        }

    async def create_subscription(
            self,
            customer: User,
            plan_id: uuid.UUID,
            customer_email: str | None,
    ) -> dict[str, Any]:
        plan = await self._plan_repo.get_by_id(plan_id)
        if not plan or not plan.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription plan not found.")

        email = customer_email or customer.email
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A customer email is required to process payment.",
            )

        business = await self._business_repo.get_with_subaccount_details(plan.business_id)
        if not business or not business.subaccounts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This business has not completed payment setup.",
            )
        subaccount_id = business.subaccounts[0].provider_subaccount_id

        total = Decimal(str(plan.price))

        # Created inactive — the billing period only starts once the first
        # charge is confirmed via the payment webhook.
        subscription = await self._subscription_repo.create(
            business_id=plan.business_id,
            customer_id=customer.id,
            plan_id=plan.id,
            plan_version=plan.version,
            status=SubscriptionStatus.inactive,
        )

        transaction_reference = await self._generate_transaction_reference()
        transaction = await self._txn_repo.create(
            business_id=plan.business_id,
            subscription_id=subscription.id,
            reference_id=transaction_reference,
            merchant_tx_ref=str(subscription.id),
            amount=total,
            currency="NGN",
        )

        charge = await self._nomba_payment.create_charge(
            amount=int(total),
            customer_email=email,
            customer_id=str(customer.id),
            subaccount_id=subaccount_id,
            order_reference=str(subscription.id),
            tokenize_card=True,
            metadata={
                "order_reference_id": str(subscription.id),
                "transaction_reference_id": transaction.reference_id,
                "operation": "subscription-payment",
                "plan_id": str(plan.id),
                "customer_id": str(customer.id),
            },
        )

        return {
            "subscription": self._to_dict(subscription),
            "transaction_reference_id": transaction.reference_id,
            "checkout_link": charge["checkout_link"],
        }

    async def get_subscription_by_id(self, current_user: User, subscription_id: uuid.UUID) -> dict[str, Any]:
        subscription = await self._subscription_repo.get_by_id(subscription_id)
        if not subscription:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found.")

        is_owning_customer = subscription.customer_id == current_user.id
        is_owning_business = False
        if current_user.role == UserRole.owner:
            business = await self._business_repo.get_by_owner(current_user.id)
            is_owning_business = bool(business and business.id == subscription.business_id)

        if not is_owning_customer and not is_owning_business:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found.")

        return self._to_dict(subscription)

    async def get_subscriptions_for_customer(
            self, customer: User, *, active_only: bool = False
    ) -> list[dict[str, Any]]:
        subscriptions = await self._subscription_repo.get_by_customer(customer.id, active_only=active_only)
        return [self._to_dict(s) for s in subscriptions]

    async def get_subscriptions_for_business(
            self, owner: User, *, active_only: bool = False
    ) -> list[dict[str, Any]]:
        business_id = await self._resolve_business(owner)
        subscriptions = await self._subscription_repo.get_by_business(business_id, active_only=active_only)
        return [self._to_dict(s) for s in subscriptions]

    async def get_active_subscriptions_for_customer(self, customer: User) -> list[dict[str, Any]]:
        return await self.get_subscriptions_for_customer(customer, active_only=True)

    async def get_active_subscriptions_for_business(self, owner: User) -> list[dict[str, Any]]:
        return await self.get_subscriptions_for_business(owner, active_only=True)
