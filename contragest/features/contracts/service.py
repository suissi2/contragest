from datetime import date, datetime
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from contragest.core.database import Contract, ContractHistory, Employee
from contragest.logic.backup import backup_service
import json

class ContractService:
    def __init__(self, session: Session):
        self.session = session

    def validate_dates(self, start_date: date, end_date: Optional[date]) -> Tuple[bool, str]:
        """Ensures start date is before end date (if end date exists)."""
        if end_date and start_date > end_date:
            return False, "Start Date cannot be after End Date."
        return True, ""

    def validate_overlap(self, employee_id: int, start_date: date, end_date: Optional[date], exclude_contract_id: int = None) -> Tuple[bool, str]:
        """
        Checks if the employee already has an active contract in the given period.
        (Simplified overlap check: checks against existing active contracts)
        """
        # Overlap logic can be complex. For now, we'll warn if there's *any* other open entry?
        # A more robust check would query for ranges.
        # Overlap exists if: (StartA <= EndB) and (EndA >= StartB)
        
        query = self.session.query(Contract).filter(Contract.employee_id == employee_id)
        if exclude_contract_id:
            query = query.filter(Contract.id != exclude_contract_id)
            
        existing_contracts = query.all()
        
        for c in existing_contracts:
            # If new contract has no end date (CDI/Permanent), it overlaps with anything starting after it
            # If existing has no end date, it overlaps with anything ending after it starts
            
            c_end = c.end_date or date.max
            new_end = end_date or date.max
            
            # Standard overlap formula: Max(start1, start2) < Min(end1, end2)
            # Here we are looking for intersection
            if max(c.start_date, start_date) <= min(c_end, new_end):
                 return False, f"Dates overlap with existing contract ({c.contract_type} starting {c.start_date})"
                 
        return True, ""

    def create_contract(self, employee_id: int, contract_type: str, start_date: date, end_date: Optional[date], user_id: int = None) -> Contract:
        # 1. Validate
        valid, msg = self.validate_dates(start_date, end_date)
        if not valid:
            raise ValueError(msg)
            
        valid, msg = self.validate_overlap(employee_id, start_date, end_date)
        if not valid:
            raise ValueError(msg)

        # 2. Create
        contract = Contract(
            employee_id=employee_id,
            contract_type=contract_type,
            start_date=start_date,
            end_date=end_date,
            version=1
        )
        self.session.add(contract)
        self.session.commit()
        
        # 3. Audit Logging
        if user_id:
            from contragest.features.auth.service import AuthService
            details = {
                "employee_id": employee_id,
                "type": contract_type,
                "start": str(start_date),
                "end": str(end_date)
            }
            AuthService().log_action(user_id, "CONTRACT_CREATED", json.dumps(details), affected_entity="CONTRACT", entity_id=contract.id)

        backup_service.create_backup()
        return contract

    def delete_contract(self, contract_id: int, user_id: int = None):
        """Deletes a contract, archives it, and cleans up employee if needed."""
        from contragest.core.database import ContractArchive
        contract = self.session.query(Contract).get(contract_id)
        if not contract:
            raise ValueError("Contract not found.")
        
        # Capture for logging
        employee_name = f"{contract.employee.first_name} {contract.employee.last_name}"
        
        # 1. Archive
        archive = ContractArchive(
            original_contract_id=contract.id,
            first_name=contract.employee.first_name,
            last_name=contract.employee.last_name,
            contract_type=contract.contract_type,
            start_date=contract.start_date,
            end_date=contract.end_date,
            version=contract.version or 1,
            reason="Deleted by user"
        )
        self.session.add(archive)
        
        employee = contract.employee
        self.session.delete(contract)
        
        # Flush to check state without committing yet
        self.session.flush()
        
        # Check if employee has any other contracts
        other_contracts_count = self.session.query(Contract).filter(Contract.employee_id == employee.id).count()
        if other_contracts_count == 0:
            self.session.delete(employee)
        
        self.session.commit()

        # 2. Audit Logging
        if user_id:
            from contragest.features.auth.service import AuthService
            AuthService().log_action(user_id, "CONTRACT_DELETED", f"Deleted contract for {employee_name}", affected_entity="CONTRACT", entity_id=contract_id)

        backup_service.create_backup()
        return True

    def recover_contract(self, archive_id: int, user_id: int = None) -> Contract:
        """Restores a contract from the archive."""
        from contragest.core.database import ContractArchive, Employee
        
        archive = self.session.query(ContractArchive).get(archive_id)
        if not archive:
            raise ValueError("Archive record not found.")
            
        # 1. Find or recreate employee
        employee = self.session.query(Employee).filter(
            Employee.first_name == archive.first_name,
            Employee.last_name == archive.last_name
        ).first()
        
        if not employee:
            employee = Employee(
                first_name=archive.first_name,
                last_name=archive.last_name
            )
            self.session.add(employee)
            self.session.flush()
            
        # 2. Recreate contract
        contract = Contract(
            employee_id=employee.id,
            contract_type=archive.contract_type,
            start_date=archive.start_date,
            end_date=archive.end_date,
            version=archive.version
        )
        self.session.add(contract)
        
        # 3. Remove from archive
        self.session.delete(archive)
        
        self.session.commit()

        # 4. Audit Logging
        if user_id:
            from contragest.features.auth.service import AuthService
            AuthService().log_action(user_id, "CONTRACT_RECOVERED", f"Recovered contract for {archive.first_name} {archive.last_name}", affected_entity="CONTRACT", entity_id=contract.id)

        backup_service.create_backup()
        return contract

    def update_contract(self, contract_id: int, first_name: str, last_name: str, contract_type: str, start_date: date, end_date: Optional[date], user_id: int = None, change_reason: str = "Updated via Service") -> Contract:
        contract = self.session.query(Contract).get(contract_id)
        if not contract:
            raise ValueError("Contract not found.")

        # 1. Validate
        valid, msg = self.validate_dates(start_date, end_date)
        if not valid:
            raise ValueError(msg)
            
        valid, msg = self.validate_overlap(contract.employee_id, start_date, end_date, exclude_contract_id=contract_id)
        if not valid:
            raise ValueError(msg)

        # 2. Check if changes exist
        if (contract.employee.first_name == first_name and
            contract.employee.last_name == last_name and
            contract.contract_type == contract_type and 
            contract.start_date == start_date and 
            contract.end_date == end_date):
            return contract # No changes

        # 3. Capture "Before" state for Audit
        before_state = {
            "first_name": contract.employee.first_name,
            "last_name": contract.employee.last_name,
            "type": contract.contract_type,
            "start": str(contract.start_date),
            "end": str(contract.end_date)
        }

        # 4. Create History Snapshot
        history = ContractHistory(
            contract_id=contract.id,
            version_number=contract.version or 1,
            first_name=contract.employee.first_name,
            last_name=contract.employee.last_name,
            contract_type=contract.contract_type,
            start_date=contract.start_date,
            end_date=contract.end_date,
            change_reason=change_reason,
            change_date=datetime.now().date()
        )
        self.session.add(history)

        # 5. Update
        contract.employee.first_name = first_name
        contract.employee.last_name = last_name
        contract.contract_type = contract_type
        contract.start_date = start_date
        contract.end_date = end_date
        contract.version = (contract.version or 1) + 1
        
        self.session.commit()

        # 6. Audit Logging
        if user_id:
            from contragest.features.auth.service import AuthService
            after_state = {
                "first_name": first_name,
                "last_name": last_name,
                "type": contract_type,
                "start": str(start_date),
                "end": str(end_date)
            }
            details = {
                "before": before_state,
                "after": after_state,
                "reason": change_reason
            }
            AuthService().log_action(user_id, "CONTRACT_UPDATED", json.dumps(details), affected_entity="CONTRACT", entity_id=contract_id)

        backup_service.create_backup()
        return contract

    def get_history(self, contract_id: int) -> List[ContractHistory]:
        return self.session.query(ContractHistory).filter(ContractHistory.contract_id == contract_id).order_by(ContractHistory.version_number.desc()).all()
