from math import ceil
import boto3
import json
from .models import RenderParams, RenderProgress, RenderResponse, RenderProgressParams


class RemotionClient:

    def __init__(self,  region, serve_url, function_name, access_key=None, secret_key=None, session=None, ):
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self.serve_url = serve_url
        self.function_name = function_name
        self.session = session
        self.client = self.create_lambda_client()

    def serializeInputProps(self, inputProps, region, type, userSpecifiedBucketName):
        try:
            payload = json.dumps(inputProps, separators=(',', ':'))
            MAX_INLINE_PAYLOAD_SIZE = 5000000 if type == 'still' else 200000

            if len(payload) > MAX_INLINE_PAYLOAD_SIZE:
                raise Exception(
                    "Warning: inputProps are over {}KB ({}KB) in size.\nThis is not currently supported.".format(
                        round(MAX_INLINE_PAYLOAD_SIZE / 1000),
                        ceil(len(payload) / 1024)
                    )
                )

            return {
                'type': 'payload',
                'payload': payload if payload is not None and payload != '' and payload != "null" else json.dumps({})
            }
        except Exception as e:
            raise Exception(
                'Error serializing inputProps. Check it has no circular references or reduce the size if the object is big.'
            )

    def create_lambda_client(self):
        if self.session:
            return self.session.client('lambda', region_name=self.region)
        elif self.access_key and self.secret_key and self.region:
            return boto3.client('lambda',
                                aws_access_key_id=self.access_key,
                                aws_secret_access_key=self.secret_key,
                                region_name=self.region)
        elif self.access_key and self.secret_key:
            return boto3.client('lambda',
                                aws_access_key_id=self.access_key,
                                aws_secret_access_key=self.secret_key)
        else:
            return boto3.client('lambda')

    def invoke_lambda(self, function_name, payload):
        try:
            response = self.client.invoke(
                FunctionName=function_name, Payload=payload)
            result = response['Payload'].read().decode('utf-8')
            decoded_result = json.loads(result)
            if decoded_result['statusCode'] != 200:
                raise Exception(
                    'Failed to invoke Lambda function'
                )
            body_object = json.loads(decoded_result['body'])

            return body_object

        except Exception as e:
            print(f"Failed to invoke Lambda function: {str(e)}")

    def contruct_render_request(self, render_params: RenderParams):
        render_params.serveUrl = self.serve_url
        render_params.region = self.region
        render_params.function_name = self.function_name
        render_params.inputProps = self.serializeInputProps(
            inputProps=render_params.data,
            region=self.region,
            type="video-or-audio",
            userSpecifiedBucketName=None)
        return json.dumps(render_params.serializeParams())

    def contruct_render_progress_request(self, render_id, bucket_name):
        progress_params = RenderProgressParams(renderId=render_id, bucketName=bucket_name,
                                               functionName=self.function_name, region=self.region)
        return json.dumps(progress_params.serializeParams())

    def render_media_on_lambda(self, render_params: RenderParams):
        params = self.contruct_render_request(render_params)
        body_object = self.invoke_lambda(function_name=self.function_name,
                                         payload=params)
        return RenderResponse(**body_object)

    def get_render_progress(self,   render_id, bucket_name):
        params = self.contruct_render_progress_request(
            render_id, bucket_name=bucket_name)
        progress_response = self.invoke_lambda(function_name=self.function_name,
                                               payload=params)

        render_progress = RenderProgress()
        render_progress.__dict__.update(progress_response)
        return render_progress
