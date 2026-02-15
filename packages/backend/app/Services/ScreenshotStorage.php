<?php

namespace App\Services;

use Aws\S3\S3Client;
use Aws\Exception\AwsException;
use Illuminate\Support\Facades\Log;

class ScreenshotStorage
{
    private S3Client $client;
    private string $bucket;
    private int $presignedUrlExpiry;
    private string $internalEndpoint;
    private string $publicUrl;

    public function __construct()
    {
        $this->internalEndpoint = config('minio.endpoint');
        $this->publicUrl = config('minio.public_url');
        $this->bucket = config('minio.bucket');
        $this->presignedUrlExpiry = config('minio.presigned_url_expiry', 15);

        $this->client = new S3Client([
            'version' => 'latest',
            'region' => config('minio.region', 'us-east-1'),
            'endpoint' => $this->internalEndpoint,
            'use_path_style_endpoint' => config('minio.use_path_style', true),
            'credentials' => [
                'key' => config('minio.access_key'),
                'secret' => config('minio.secret_key'),
            ],
        ]);

        $this->ensureBucketExists();
    }

    /**
     * Ensure the bucket exists, creating it if necessary.
     */
    private function ensureBucketExists(): void
    {
        try {
            if (!$this->client->doesBucketExist($this->bucket)) {
                $this->client->createBucket([
                    'Bucket' => $this->bucket,
                ]);
                Log::info("Created MinIO bucket: {$this->bucket}");
            }
        } catch (AwsException $e) {
            Log::warning("Failed to check/create MinIO bucket: " . $e->getMessage());
        }
    }

    /**
     * Generate a presigned URL for a screenshot.
     */
    public function getPresignedUrl(string $key): ?string
    {
        try {
            $cmd = $this->client->getCommand('GetObject', [
                'Bucket' => $this->bucket,
                'Key' => $key,
            ]);

            $request = $this->client->createPresignedRequest($cmd, "+{$this->presignedUrlExpiry} minutes");

            $presignedUrl = (string) $request->getUri();

            // Replace internal endpoint with public URL if they differ
            if ($this->publicUrl !== $this->internalEndpoint) {
                $presignedUrl = str_replace($this->internalEndpoint, $this->publicUrl, $presignedUrl);
            }

            return $presignedUrl;
        } catch (AwsException $e) {
            Log::error("Failed to generate presigned URL: " . $e->getMessage());
            return null;
        }
    }

    /**
     * Check if a screenshot exists in MinIO.
     */
    public function exists(string $key): bool
    {
        try {
            return $this->client->doesObjectExist($this->bucket, $key);
        } catch (AwsException $e) {
            Log::error("Failed to check if screenshot exists: " . $e->getMessage());
            return false;
        }
    }

    /**
     * Delete a screenshot from MinIO.
     */
    public function delete(string $key): bool
    {
        try {
            $this->client->deleteObject([
                'Bucket' => $this->bucket,
                'Key' => $key,
            ]);
            return true;
        } catch (AwsException $e) {
            Log::error("Failed to delete screenshot: " . $e->getMessage());
            return false;
        }
    }

    /**
     * Get the size of a screenshot in bytes.
     */
    public function getSize(string $key): ?int
    {
        try {
            $result = $this->client->headObject([
                'Bucket' => $this->bucket,
                'Key' => $key,
            ]);
            return $result['ContentLength'] ?? null;
        } catch (AwsException $e) {
            return null;
        }
    }

    /**
     * List all screenshots with metadata.
     */
    public function listAll(): array
    {
        $screenshots = [];

        try {
            $result = $this->client->listObjectsV2([
                'Bucket' => $this->bucket,
            ]);

            foreach ($result['Contents'] ?? [] as $object) {
                $screenshots[] = [
                    'key' => $object['Key'],
                    'size' => $object['Size'],
                    'last_modified' => $object['LastModified']->format('c'),
                ];
            }
        } catch (AwsException $e) {
            Log::error("Failed to list screenshots: " . $e->getMessage());
        }

        return $screenshots;
    }

    /**
     * Get storage statistics.
     */
    public function getStats(): array
    {
        $totalSize = 0;
        $count = 0;

        try {
            $result = $this->client->listObjectsV2([
                'Bucket' => $this->bucket,
            ]);

            foreach ($result['Contents'] ?? [] as $object) {
                $totalSize += $object['Size'];
                $count++;
            }
        } catch (AwsException $e) {
            Log::error("Failed to get storage stats: " . $e->getMessage());
        }

        return [
            'total_size' => $totalSize,
            'count' => $count,
        ];
    }

    /**
     * Delete screenshots older than a given date.
     */
    public function deleteOlderThan(\DateTimeInterface $cutoffDate): int
    {
        $deleted = 0;

        try {
            $result = $this->client->listObjectsV2([
                'Bucket' => $this->bucket,
            ]);

            foreach ($result['Contents'] ?? [] as $object) {
                if ($object['LastModified'] < $cutoffDate) {
                    $this->delete($object['Key']);
                    $deleted++;
                }
            }
        } catch (AwsException $e) {
            Log::error("Failed to delete old screenshots: " . $e->getMessage());
        }

        return $deleted;
    }

    /**
     * Get the bucket name.
     */
    public function getBucket(): string
    {
        return $this->bucket;
    }

    /**
     * Get the presigned URL expiry in minutes.
     */
    public function getPresignedUrlExpiry(): int
    {
        return $this->presignedUrlExpiry;
    }
}
