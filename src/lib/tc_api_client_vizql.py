from dataclasses import dataclass
from typing import List

from src.lib.tc_api_client import tc_api_version, TCApiClient


@dataclass
class PublishedDataSource:
    luid: str = None
    name: str = None
    contentUrl: str = None
    type: str = None
    createdAt: str = None
    updatedAt: str = None
    project_luid: str = None
    project_name: str = None
    owner_name: str = None

@dataclass
class DataSourceMetadata:

    fieldName: str = None
    fieldCaption: str = None
    dataType: str = None
    logicalTableId: str = None

class TCApiClientVizQl(TCApiClient):
    def get_datasource_metadata(self, datasource_luid, json_response: bool = True) -> List[DataSourceMetadata]:
        payload = {
            "datasource": {
                "datasourceLuid": datasource_luid
            }
        }
        response = self._post_public("/api/v1/vizql-data-service/read-metadata", payload)
        if json_response:
            return response["data"]
        else:
            metadata = []
            for field in response['data']:
                metadata.append(DataSourceMetadata(
                    fieldName=field['fieldName'],
                    fieldCaption=field['fieldCaption'],
                    dataType=field['dataType'],
                    logicalTableId=field['logicalTableId']
                ))
            return metadata

    def query_datasource(self, pds: PublishedDataSource, query: dict) -> dict:
        """Queries a datasource using the VizQL Data Service
        """
        payload = {
            "datasource": {
                "datasourceLuid": pds.luid
            },
            "query": query
        }
        url_part = f"/api/v1/vizql-data-service/query-datasource"
        r = self._post_public(url_part, payload)
        return r

    def get_datasources_list(self) -> List[PublishedDataSource]:
        """Gets a list of published datasources
        Returns:
            List[PublishedDataSource]: List of published datasources including their details
        """
        response = self._get_public(f"/api/{tc_api_version}/sites/{self.site_luid}/datasources")
        datasources = []

        for ds in response['datasources']['datasource']:
            datasource = PublishedDataSource(
                luid=ds['id'],
                name=ds['name'],
                contentUrl=ds.get('contentUrl'),
                type=ds.get('type'),
                createdAt=ds.get('createdAt'),
                updatedAt=ds.get('updatedAt'),
                project_luid=ds.get('project', {}).get('id'),
                project_name=ds.get('project', {}).get('name'),
                owner_name=ds.get('owner', {}).get('name')
            )
            datasources.append(datasource)

        return datasources



