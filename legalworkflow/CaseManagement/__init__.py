import azure.functions as func
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import os
from azure.storage.blob import BlobServiceClient
from azure.cosmos import CosmosClient
import uuid

logger = logging.getLogger(__name__)

class CaseManager:
    """Legal case management service."""
    
    def __init__(self):
        """Initialize case manager with database connections."""
        self.cosmos_endpoint = os.environ.get('COSMOS_DB_ENDPOINT')
        self.cosmos_key = os.environ.get('COSMOS_DB_KEY')
        
        if self.cosmos_endpoint and self.cosmos_key:
            self.cosmos_client = CosmosClient(self.cosmos_endpoint, self.cosmos_key)
            self.database = self.cosmos_client.get_database_client('LegalWorkflow')
            self.cases_container = self.database.get_container_client('Cases')
    
    def create_case(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new legal case."""
        try:
            case_id = str(uuid.uuid4())
            case = {
                'id': case_id,
                'case_number': case_data.get('case_number'),
                'title': case_data.get('title'),
                'description': case_data.get('description'),
                'client_name': case_data.get('client_name'),
                'client_contact': case_data.get('client_contact'),
                'case_type': case_data.get('case_type'),
                'priority': case_data.get('priority', 'medium'),
                'status': case_data.get('status', 'open'),
                'assigned_attorney': case_data.get('assigned_attorney'),
                'created_date': datetime.utcnow().isoformat(),
                'modified_date': datetime.utcnow().isoformat(),
                'deadline': case_data.get('deadline'),
                'estimated_hours': case_data.get('estimated_hours'),
                'billable_rate': case_data.get('billable_rate'),
                'documents': [],
                'tasks': [],
                'notes': case_data.get('notes', []),
                'metadata': case_data.get('metadata', {})
            }
            
            # Save to database if configured
            if hasattr(self, 'cases_container'):
                self.cases_container.create_item(body=case)
            
            logger.info(f"Created case: {case_id}")
            return {
                'status': 'success',
                'case_id': case_id,
                'case': case
            }
        except Exception as e:
            logger.error(f"Failed to create case: {str(e)}")
            raise e
    
    def get_case(self, case_id: str) -> Dict[str, Any]:
        """Retrieve a specific case by ID."""
        try:
            if hasattr(self, 'cases_container'):
                case = self.cases_container.read_item(item=case_id, partition_key=case_id)
                return {
                    'status': 'success',
                    'case': case
                }
            else:
                return {
                    'status': 'error',
                    'message': 'Database not configured'
                }
        except Exception as e:
            logger.error(f"Failed to retrieve case {case_id}: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def update_case(self, case_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing case."""
        try:
            if hasattr(self, 'cases_container'):
                # Get existing case
                existing_case = self.cases_container.read_item(item=case_id, partition_key=case_id)
                
                # Apply updates
                existing_case.update(updates)
                existing_case['modified_date'] = datetime.utcnow().isoformat()
                
                # Save updated case
                self.cases_container.replace_item(item=case_id, body=existing_case)
                
                return {
                    'status': 'success',
                    'case_id': case_id,
                    'case': existing_case
                }
            else:
                return {
                    'status': 'error',
                    'message': 'Database not configured'
                }
        except Exception as e:
            logger.error(f"Failed to update case {case_id}: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def list_cases(self, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """List cases with optional filtering."""
        try:
            if hasattr(self, 'cases_container'):
                query = "SELECT * FROM c"
                parameters = []
                
                if filters:
                    conditions = []
                    if filters.get('status'):
                        conditions.append("c.status = @status")
                        parameters.append({'name': '@status', 'value': filters['status']})
                    if filters.get('assigned_attorney'):
                        conditions.append("c.assigned_attorney = @attorney")
                        parameters.append({'name': '@attorney', 'value': filters['assigned_attorney']})
                    if filters.get('case_type'):
                        conditions.append("c.case_type = @type")
                        parameters.append({'name': '@type', 'value': filters['case_type']})
                    
                    if conditions:
                        query += " WHERE " + " AND ".join(conditions)
                
                cases = list(self.cases_container.query_items(
                    query=query,
                    parameters=parameters,
                    enable_cross_partition_query=True
                ))
                
                return {
                    'status': 'success',
                    'cases': cases,
                    'count': len(cases)
                }
            else:
                return {
                    'status': 'error',
                    'message': 'Database not configured'
                }
        except Exception as e:
            logger.error(f"Failed to list cases: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def archive_case(self, case_id: str) -> Dict[str, Any]:
        """Archive a case (soft delete)."""
        try:
            return self.update_case(case_id, {
                'status': 'archived',
                'archived_date': datetime.utcnow().isoformat()
            })
        except Exception as e:
            logger.error(f"Failed to archive case {case_id}: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }

def main(req: func.HttpRequest) -> func.HttpResponse:
    """Main case management function handler."""
    try:
        case_manager = CaseManager()
        method = req.method.upper()
        
        if method == "POST":
            # Create new case
            try:
                req_body = req.get_json()
                if not req_body:
                    return func.HttpResponse(
                        json.dumps({'status': 'error', 'message': 'Invalid JSON body'}),
                        status_code=400,
                        mimetype="application/json"
                    )
                
                result = case_manager.create_case(req_body)
                return func.HttpResponse(
                    json.dumps(result),
                    status_code=201,
                    mimetype="application/json"
                )
            except Exception as e:
                return func.HttpResponse(
                    json.dumps({'status': 'error', 'message': str(e)}),
                    status_code=400,
                    mimetype="application/json"
                )
        
        elif method == "GET":
            # Get case(s)
            case_id = req.params.get('id')
            
            if case_id:
                # Get specific case
                result = case_manager.get_case(case_id)
                status_code = 200 if result['status'] == 'success' else 404
            else:
                # List cases with optional filters
                filters = {}
                if req.params.get('status'):
                    filters['status'] = req.params.get('status')
                if req.params.get('assigned_attorney'):
                    filters['assigned_attorney'] = req.params.get('assigned_attorney')
                if req.params.get('case_type'):
                    filters['case_type'] = req.params.get('case_type')
                
                result = case_manager.list_cases(filters)
                status_code = 200 if result['status'] == 'success' else 500
            
            return func.HttpResponse(
                json.dumps(result),
                status_code=status_code,
                mimetype="application/json"
            )
        
        elif method == "PUT":
            # Update case
            case_id = req.params.get('id')
            if not case_id:
                return func.HttpResponse(
                    json.dumps({'status': 'error', 'message': 'Case ID required'}),
                    status_code=400,
                    mimetype="application/json"
                )
            
            try:
                req_body = req.get_json()
                if not req_body:
                    return func.HttpResponse(
                        json.dumps({'status': 'error', 'message': 'Invalid JSON body'}),
                        status_code=400,
                        mimetype="application/json"
                    )
                
                result = case_manager.update_case(case_id, req_body)
                status_code = 200 if result['status'] == 'success' else 404
                
                return func.HttpResponse(
                    json.dumps(result),
                    status_code=status_code,
                    mimetype="application/json"
                )
            except Exception as e:
                return func.HttpResponse(
                    json.dumps({'status': 'error', 'message': str(e)}),
                    status_code=400,
                    mimetype="application/json"
                )
        
        elif method == "DELETE":
            # Archive case
            case_id = req.params.get('id')
            if not case_id:
                return func.HttpResponse(
                    json.dumps({'status': 'error', 'message': 'Case ID required'}),
                    status_code=400,
                    mimetype="application/json"
                )
            
            result = case_manager.archive_case(case_id)
            status_code = 200 if result['status'] == 'success' else 404
            
            return func.HttpResponse(
                json.dumps(result),
                status_code=status_code,
                mimetype="application/json"
            )
        
        else:
            return func.HttpResponse(
                json.dumps({'status': 'error', 'message': 'Method not allowed'}),
                status_code=405,
                mimetype="application/json"
            )
    
    except Exception as e:
        logger.error(f"Case management error: {str(e)}")
        return func.HttpResponse(
            json.dumps({'status': 'error', 'message': 'Internal server error'}),
            status_code=500,
            mimetype="application/json"
        )