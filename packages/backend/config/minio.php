<?php

return [

    /*
    |--------------------------------------------------------------------------
    | MinIO Configuration
    |--------------------------------------------------------------------------
    |
    | Configuration for MinIO S3-compatible object storage.
    |
    */

    'endpoint' => env('MINIO_ENDPOINT', 'http://minio:9000'),

    'access_key' => env('MINIO_ACCESS_KEY', 'formbot'),

    'secret_key' => env('MINIO_SECRET_KEY', 'formbot-secret-key'),

    'bucket' => env('MINIO_BUCKET', 'formbot-screenshots'),

    'use_path_style' => env('MINIO_USE_PATH_STYLE', true),

    'region' => env('MINIO_REGION', 'us-east-1'),

    /*
    |--------------------------------------------------------------------------
    | Presigned URL Expiry
    |--------------------------------------------------------------------------
    |
    | The number of minutes before presigned URLs expire.
    |
    */
    'presigned_url_expiry' => env('MINIO_PRESIGNED_URL_EXPIRY', 15),

];
