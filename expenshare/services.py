from abc import ABC, abstractmethod
from collections import defaultdict
from django.core.exceptions import PermissionDenied
from .models import Credit, Debt, Sharelist
from django.contrib.auth.models import User


class BaseService(ABC):
    @abstractmethod
    def validate(self):
        pass

    @abstractmethod
    def execute(self):
        pass


class CreditCreateService(BaseService):
    def __init__(self, sharelist_id, debtor_ids, creditor_id, credit_name, credit_datetime, credit_amount):
        self._sharelist_id = sharelist_id
        self._debtor_ids = debtor_ids
        self._creditor_id = creditor_id
        self._credit_name = credit_name
        self._credit_datetime = credit_datetime
        self._credit_amount = credit_amount

    def execute(self):
        self.validate()

        credit = Credit(
            name=self._credit_name, 
            datetime=self._credit_datetime, 
            amount=self._credit_amount,
            creditor_id=self._creditor_id,
            sharelist_id=self._sharelist_id)
        credit.save()

        debtors_to_amount = self._compute_debts()

        Debt.objects.bulk_create(
            [Debt(debtor_id=dbtr_id, credit=credit, amount=amnt) for dbtr_id, amnt in debtors_to_amount.items()]
        )

    def validate(self):
        if not Sharelist.objects.are_in_sharelist(self._sharelist_id, self._debtor_ids + [self._creditor_id]):
            raise ValueError('Debtors and creditor should be in the same sharelist')

    def _compute_debts(self):
        debt = self._credit_amount / len(self._debtor_ids)
        debtors_to_amount = {u_id: debt for u_id in self._debtor_ids}
        return debtors_to_amount


class CreditInfoService(BaseService):
    def __init__(self, sharelist_id, credit_id, user_id):
        self._sharelist_id = sharelist_id
        self._credit_id = credit_id
        self._user_id = user_id

    def execute(self):
        self.validate()

        credit = Credit.objects.filter(id=self._credit_id).prefetch_related('debts')[0]
        debts = {d.debtor_id: d for d in credit.debts.all()}

        sharelist_members = User.objects.filter(sharelist=self._sharelist_id).select_related('profile').all()
        sharelist_members = {u.id: u for u in sharelist_members}

        debts = [
            {
                'username': sharelist_members[user_id].username,
                'photo': sharelist_members[user_id].profile.photo,
                'amount': debts[user_id].amount if user_id in debts else 0.0,
            }
            for user_id in sharelist_members
        ]

        info = {
            'name': credit.name,
            'amount': credit.amount,
            'datetime': credit.datetime,
            'debts': debts,
        }

        return info

    def validate(self):
        if not Sharelist.objects.are_in_sharelist(self._sharelist_id, [self._user_id]):
            raise PermissionDenied('User is not authorized to view this credit')
