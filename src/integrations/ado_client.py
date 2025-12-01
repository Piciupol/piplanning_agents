"""Azure DevOps client wrapper."""
import os
import json
import requests
import base64
from typing import List, Optional, Dict, Any
from azure.devops.connection import Connection
from azure.devops.v7_0.work_item_tracking.models import Wiql
from msrest.authentication import BasicAuthentication
from msrest.exceptions import AuthenticationError
from requests.auth import HTTPBasicAuth

from src.core.models import Feature, FeatureStatus, Priority, Team, UserStory, Milestone
from datetime import datetime
from src.utils.config import Config


class ADOClient:
    """Wrapper for Azure DevOps API."""
    
    def __init__(self, organization_url: Optional[str] = None, personal_access_token: Optional[str] = None):
        """Initialize ADO client."""
        self.org_url = organization_url or Config.ADO_ORG_URL
        self.pat = personal_access_token or Config.ADO_PAT
        self.connection = None
        
        if self.org_url and self.pat:
            try:
                org_url_clean = self.org_url.rstrip('/')
                print(f"DEBUG: Connecting to ADO with URL: {org_url_clean}")
                credentials = BasicAuthentication("", self.pat)
                self.connection = Connection(base_url=org_url_clean, creds=credentials)
                try:
                    core_client = self.connection.clients.get_core_client()
                    projects = core_client.get_projects()
                    print(f"ADO connection successful. Found {len(projects)} projects.")
                except Exception as conn_test_error:
                    print(f"ADO connection test failed: {conn_test_error}")
                    self.connection = None
            except Exception as e:
                print(f"Warning: Could not initialize ADO connection: {e}")
                self.connection = None
    
    def is_connected(self) -> bool:
        return self.connection is not None
    
    def _get_work_items_in_batches(self, wit_client, work_item_ids: List[int], project: Optional[str] = None, batch_size: int = 200) -> List[Any]:
        """
        Fetch work items in batches to avoid 414 URI Too Long error.
        
        Args:
            wit_client: Work Item Tracking client
            work_item_ids: List of work item IDs
            project: Project name (optional)
            batch_size: Number of IDs per batch (default 200)
            
        Returns:
            List of work items
        """
        all_work_items = []
        total_batches = (len(work_item_ids) + batch_size - 1) // batch_size
        
        for i in range(0, len(work_item_ids), batch_size):
            batch = work_item_ids[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            if total_batches > 1:
                print(f"DEBUG: Fetching batch {batch_num}/{total_batches} ({len(batch)} items)...")
            try:
                if project:
                    batch_items = wit_client.get_work_items(ids=batch, project=project)
                else:
                    batch_items = wit_client.get_work_items(ids=batch)
                all_work_items.extend(batch_items)
            except Exception as e:
                print(f"WARNING: Failed to fetch batch {batch_num}: {e}")
                # Continue with next batch
                continue
        
        return all_work_items
    
    def fetch_features(self, project: str, area_path: Optional[str] = None, iteration_path: Optional[str] = None, wiql_query: Optional[str] = None, query_id: Optional[str] = None) -> List[Feature]:
        """Fetch features from ADO."""
        if not self.is_connected(): return []
        
        try:
            wit_client = self.connection.clients.get_work_item_tracking_client()
            
            if query_id:
                features = self._fetch_features_from_query_id(wit_client, project, query_id)
                # If query_id failed and returned empty, fall back to standard query
                if not features:
                    print(f"WARNING: Query ID '{query_id}' returned no results. Falling back to standard WIQL query...")
                else:
                    return features
            
            if not wiql_query:
                where_clauses = [
                    f"[System.TeamProject] = '{project}'",
                    f"[{Config.get_field('work_item_type')}] IN ('Feature', 'Epic')",
                    f"[{Config.get_field('state')}] <> 'Closed'"
                ]
                if area_path:
                    escaped = area_path.replace("'", "''").replace("\\", "\\\\")
                    where_clauses.append(f"[{Config.get_field('area_path')}] UNDER '{escaped}'")
                if iteration_path:
                    escaped = iteration_path.replace("'", "''").replace("\\", "\\\\")
                    where_clauses.append(f"[{Config.get_field('iteration_path')}] UNDER '{escaped}'")
                
                where_clause = " AND ".join(where_clauses)
                wiql_query = f"""
                SELECT [System.Id], [{Config.get_field('title')}], [{Config.get_field('state')}], 
                       [{Config.get_field('area_path')}], [{Config.get_field('iteration_path')}], 
                       [{Config.get_field('priority')}]
                FROM WorkItems
                WHERE {where_clause}
                ORDER BY [System.Id]
                """
            
            print(f"DEBUG: Executing WIQL query...")
            wiql = Wiql(query=wiql_query)
            query_result = wit_client.query_by_wiql(wiql)
            
            if not query_result.work_items: return []
            
            work_item_ids = [wi.id for wi in query_result.work_items]
            print(f"DEBUG: Found {len(work_item_ids)} work items, fetching in batches...")
            
            # Fetch work items in batches to avoid 414 URI Too Long error
            work_items = self._get_work_items_in_batches(wit_client, work_item_ids, project)
            
            features = []
            for wi in work_items:
                features.append(self._process_work_item_to_feature(wi, wit_client, project))
            return features
        except Exception as e:
            import traceback
            print(f"ERROR fetching features from ADO: {e}")
            traceback.print_exc()
            return []
    
    def _process_work_item_to_feature(self, wi, wit_client, project):
        fields = wi.fields
        
        # Map priority
        priority_val = fields.get(Config.get_field("priority"), 2)
        if priority_val <= 1: priority = Priority.CRITICAL
        elif priority_val <= 2: priority = Priority.HIGH
        elif priority_val <= 3: priority = Priority.MEDIUM
        else: priority = Priority.LOW
        
        # Map state
        state_str = fields.get(Config.get_field("state"), "New").lower()
        if "new" in state_str: status = FeatureStatus.NEW
        elif "active" in state_str or "in progress" in state_str: status = FeatureStatus.ACTIVE
        elif "resolved" in state_str: status = FeatureStatus.RESOLVED
        else: status = FeatureStatus.CLOSED
        
        user_stories, dependencies = self._fetch_user_stories_for_feature(wit_client, project, wi.id)
        milestones = self._fetch_milestones_for_feature(wit_client, project, wi.id)
        
        deadline_sprint = None
        if milestones:
            milestone_sprints = [m.sprint for m in milestones if m.sprint]
            if milestone_sprints: deadline_sprint = milestone_sprints[0]
        
        owner_name = self._extract_team_name(fields.get(Config.get_field("assigned_to")))
        feature_team = self._map_owner_to_team(owner_name)
        
        if not feature_team:
            area_path = fields.get(Config.get_field("area_path"), "")
            default_team_names = Config.get_default_team_names()
            for team_name in default_team_names:
                if team_name in area_path:
                    feature_team = team_name
                    break
        
        if feature_team:
            default_team_names = Config.get_default_team_names()
            for us in user_stories + dependencies:
                if not us.assigned_team or (us.assigned_team and us.assigned_team not in default_team_names):
                    us.assigned_team = feature_team
        
        return Feature(
            id=wi.id,
            title=fields.get(Config.get_field("title"), "Untitled"),
            description=fields.get(Config.get_field("description"), ""),
            area_path=fields.get(Config.get_field("area_path")),
            iteration_path=fields.get(Config.get_field("iteration_path")),
            state=status,
            priority=priority,
            business_value=fields.get(Config.get_field("business_value")),
            effort=fields.get(Config.get_field("effort")),
            milestones=milestones,
            deadline_sprint=deadline_sprint,
            user_stories=user_stories + dependencies,
            assigned_team=feature_team
        )

    def fetch_teams(self, project: str) -> List[Team]:
        if not self.is_connected(): return []
        try:
            core_client = self.connection.clients.get_core_client()
            projects = core_client.get_projects()
            project_obj = next((p for p in projects if p.name == project), None)
            if not project_obj: return []
            teams = core_client.get_teams(project_id=project_obj.id)
            return [Team(id=t.id, name=t.name, capacity_per_iteration=40) for t in teams]
        except Exception as e:
            print(f"ERROR fetching teams: {e}")
            return []
    
    def _fetch_user_stories_for_feature(self, wit_client, project, feature_id, team_area_path=None):
        direct_user_stories = []
        dependencies = []
        try:
            org_url_clean = self.org_url.rstrip('/').replace('/GN', '').replace('/ONEGN', '')
            if not org_url_clean.endswith('/ONEGN') and 'ONEGN' in self.org_url:
                 org_url_clean = org_url_clean.split('/ONEGN')[0] + '/ONEGN'
            else:
                 org_url_clean = self.org_url.rstrip('/')
            
            api_url = f"{org_url_clean}/{project}/_apis/wit/workitems/{feature_id}"
            params = {'$expand': 'relations', 'api-version': '7.1'}
            response = requests.get(api_url, params=params, auth=HTTPBasicAuth('', self.pat), headers={'Content-Type': 'application/json'})
            
            work_item_ids = set()
            if response.status_code == 200:
                work_item_data = response.json()
                if 'relations' in work_item_data:
                    for relation in work_item_data['relations']:
                        relation_url = relation.get('url', '')
                        if relation_url:
                            try:
                                url_parts = relation_url.split('/')
                                workitems_idx = None
                                for i, part in enumerate(url_parts):
                                    if part.lower() == 'workitems':
                                        workitems_idx = i
                                        break
                                if workitems_idx is not None and workitems_idx + 1 < len(url_parts):
                                    work_item_ids.add(int(url_parts[workitems_idx + 1].split('?')[0]))
                            except: continue
            
            if not work_item_ids: return [], []
            # Fetch in batches (usually small list, but safe to batch anyway)
            work_items = self._get_work_items_in_batches(wit_client, list(work_item_ids), project, batch_size=200)
            
            for wi in work_items:
                fields = wi.fields
                work_item_type = fields.get(Config.get_field("work_item_type"), "").lower()
                title = fields.get(Config.get_field("title"), "")
                area_path = fields.get(Config.get_field("area_path"), "")
                
                if work_item_type not in ["user story", "dependency"]: continue
                
                is_dependency = (work_item_type == "dependency") or (title.startswith("[From") and "to Ivy]" in title)
                
                if team_area_path and not is_dependency:
                    if team_area_path not in area_path: continue
                
                status_map = {"new": FeatureStatus.NEW, "active": FeatureStatus.ACTIVE, "resolved": FeatureStatus.RESOLVED, "closed": FeatureStatus.CLOSED}
                state_str = fields.get(Config.get_field("state"), "New").lower()
                status = next((v for k, v in status_map.items() if k in state_str), FeatureStatus.CLOSED)

                # Only consider User Stories in "new" or "active" state
                if status not in [FeatureStatus.NEW, FeatureStatus.ACTIVE]:
                    continue

                # For active stories, prefer remaining_work over effort
                # For new stories, use effort
                effort_value = None
                remaining_work_value = None
                
                if status == FeatureStatus.ACTIVE:
                    remaining_work_value = fields.get(Config.get_field("remaining_work"))
                    # If remaining_work is not available, fall back to effort
                    if remaining_work_value is None:
                        effort_value = fields.get(Config.get_field("effort"))
                else:  # NEW
                    effort_value = fields.get(Config.get_field("effort"))

                user_story = UserStory(
                    id=wi.id,
                    title=title,
                    description=fields.get(Config.get_field("description"), ""),
                    feature_id=feature_id,
                    assigned_team=self._extract_team_name(fields.get(Config.get_field("assigned_to"))),
                    effort=effort_value,
                    remaining_work=remaining_work_value,
                    state=status
                )
                
                if is_dependency: dependencies.append(user_story)
                else: direct_user_stories.append(user_story)
                    
            return direct_user_stories, dependencies
        except Exception as e:
            print(f"Warning: Could not fetch User Stories for feature {feature_id}: {e}")
            return [], []
    
    def _fetch_milestones_for_feature(self, wit_client, project, feature_id):
        milestones = []
        try:
            org_url_clean = self.org_url.rstrip('/').replace('/GN', '').replace('/ONEGN', '')
            if not org_url_clean.endswith('/ONEGN') and 'ONEGN' in self.org_url:
                 org_url_clean = org_url_clean.split('/ONEGN')[0] + '/ONEGN'
            else:
                 org_url_clean = self.org_url.rstrip('/')

            api_url = f"{org_url_clean}/{project}/_apis/wit/workitems/{feature_id}"
            params = {'$expand': 'relations', 'api-version': '7.1'}
            response = requests.get(api_url, params=params, auth=HTTPBasicAuth('', self.pat), headers={'Content-Type': 'application/json'})
            
            work_item_ids = set()
            if response.status_code == 200:
                work_item_data = response.json()
                if 'relations' in work_item_data:
                    for relation in work_item_data['relations']:
                        relation_url = relation.get('url', '')
                        if relation_url:
                            try:
                                url_parts = relation_url.split('/')
                                workitems_idx = None
                                for i, part in enumerate(url_parts):
                                    if part.lower() == 'workitems':
                                        workitems_idx = i
                                        break
                                if workitems_idx is not None and workitems_idx + 1 < len(url_parts):
                                    work_item_ids.add(int(url_parts[workitems_idx + 1].split('?')[0]))
                            except: continue
            
            if not work_item_ids: return []
            # Fetch in batches (usually small list, but safe to batch anyway)
            work_items = self._get_work_items_in_batches(wit_client, list(work_item_ids), project, batch_size=200)
            
            for wi in work_items:
                fields = wi.fields
                if fields.get(Config.get_field("work_item_type"), "").lower() != "milestone": continue
                
                target_date_str = fields.get(Config.get_field("target_date"))
                # Fallback for target date if mapped field is missing
                if not target_date_str:
                    target_date_str = (
                        fields.get("System.TargetDate") or 
                        fields.get("Microsoft.VSTS.Scheduling.TargetDate")
                    )
                
                target_date = None
                if target_date_str:
                    try:
                        if isinstance(target_date_str, str):
                            target_date = datetime.fromisoformat(target_date_str.replace('Z', '+00:00'))
                        elif isinstance(target_date_str, datetime):
                            target_date = target_date_str
                    except: pass
                
                milestones.append(Milestone(
                    id=wi.id,
                    title=fields.get(Config.get_field("title"), "Untitled"),
                    target_date=target_date
                ))
            return milestones
        except Exception as e:
            print(f"Warning: Could not fetch Milestones: {e}")
            return []

    def _extract_team_name(self, assigned_to) -> Optional[str]:
        if assigned_to is None: return None
        if isinstance(assigned_to, str): return assigned_to
        if isinstance(assigned_to, dict):
            return assigned_to.get("displayName") or assigned_to.get("uniqueName") or assigned_to.get("name")
        return str(assigned_to)

    def _map_owner_to_team(self, owner_name: Optional[str]) -> Optional[str]:
        if not owner_name: return None
        owner_lower = owner_name.lower()
        for owner_key, team_name in Config.OWNER_MAPPING.items():
            key_lower = owner_key.lower()
            if key_lower in owner_lower: return team_name
            if "ł" in key_lower:
                if key_lower.replace("ł", "l") in owner_lower.replace("ł", "l"): return team_name
        return None

    def _fetch_features_from_query_id(self, wit_client, project, query_id):
        try:
            org_url_clean = self.org_url.rstrip('/')
            
            # Try to get query definition first (to extract WIQL)
            # This works for both Personal and Shared queries
            query_def_urls = [
                f"{org_url_clean}/{project}/_apis/wit/queries/{query_id}?$expand=wiql&api-version=7.1",
                f"{org_url_clean}/{project}/_apis/wit/queries/Shared Queries/{query_id}?$expand=wiql&api-version=7.1",
            ]
            
            print(f"DEBUG: Fetching query definition for Query ID: {query_id}")
            
            credentials = base64.b64encode(f":{self.pat}".encode()).decode()
            headers = {"Authorization": f"Basic {credentials}", "Content-Type": "application/json"}
            
            query_wiql = None
            for query_def_url in query_def_urls:
                try:
                    response = requests.get(query_def_url, headers=headers, timeout=30)
                    if response.status_code == 200:
                        query_data = response.json()
                        query_wiql = query_data.get("wiql")
                        if query_wiql:
                            print(f"DEBUG: Successfully retrieved WIQL from query definition")
                            break
                except:
                    continue
            
            # If we got WIQL, execute it directly
            if query_wiql:
                print(f"DEBUG: Executing WIQL from query definition...")
                wiql = Wiql(query=query_wiql)
                query_result = wit_client.query_by_wiql(wiql)
                
                if not query_result.work_items:
                    print(f"WARNING: Query returned no work items")
                    return []
                
                work_item_ids = [wi.id for wi in query_result.work_items]
                print(f"DEBUG: Found {len(work_item_ids)} work items from query")
                
                # Fetch work items in batches to avoid 414 URI Too Long error
                work_items = self._get_work_items_in_batches(wit_client, work_item_ids, project)
                
                features = []
                for wi in work_items:
                    features.append(self._process_work_item_to_feature(wi, wit_client, project))
                
                print(f"DEBUG: Successfully processed {len(features)} features from query")
                return features
            
            # Fallback: Try direct results endpoint
            print(f"DEBUG: Could not get query definition, trying direct results endpoint...")
            query_results_url = f"{org_url_clean}/{project}/_apis/wit/queries/{query_id}/results?api-version=7.1"
            
            response = requests.get(query_results_url, headers=headers, timeout=30)
            if response.status_code != 200:
                error_msg = f"Query failed with status {response.status_code}"
                try:
                    error_body = response.json()
                    if "message" in error_body:
                        error_msg += f": {error_body['message']}"
                except:
                    error_msg += f": {response.text[:200]}"
                
                print(f"ERROR: {error_msg}")
                print(f"DEBUG: Query ID '{query_id}' may be invalid or you may not have access to it.")
                return []
            
            query_data = response.json()
            if not query_data.get("value"):
                print(f"WARNING: Query returned no results")
                return []
            
            work_item_ids = [item["id"] for item in query_data["value"]]
            print(f"DEBUG: Found {len(work_item_ids)} work items from query results")
            
            if not work_item_ids:
                return []
            
            # Fetch work items in batches to avoid 414 URI Too Long error
            work_items = self._get_work_items_in_batches(wit_client, work_item_ids, project)
            
            features = []
            for wi in work_items:
                features.append(self._process_work_item_to_feature(wi, wit_client, project))
            
            print(f"DEBUG: Successfully processed {len(features)} features from query")
            return features
        except Exception as e:
            import traceback
            print(f"ERROR fetching features from query ID '{query_id}': {e}")
            traceback.print_exc()
            return []
