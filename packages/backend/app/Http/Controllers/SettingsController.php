<?php

namespace App\Http\Controllers;

use App\Models\AppSetting;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Redis;

class SettingsController extends Controller
{
    /**
     * Display all application settings.
     */
    public function index(): JsonResponse
    {
        $settings = AppSetting::all()->pluck('value', 'key');

        return response()->json($settings);
    }

    /**
     * Update application settings.
     */
    public function update(Request $request): JsonResponse
    {
        $validated = $request->validate([
            'settings' => ['required', 'array'],
            'settings.*.key' => ['required', 'string'],
            'settings.*.value' => ['required', 'string'],
        ]);

        foreach ($validated['settings'] as $setting) {
            AppSetting::set($setting['key'], $setting['value']);
        }

        $settings = AppSetting::all()->pluck('value', 'key');

        return response()->json($settings);
    }

    /**
     * Health check endpoint.
     */
    public function health(): JsonResponse
    {
        $status = ['status' => 'ok', 'services' => []];

        // Check database connection
        try {
            DB::connection()->getPdo();
            $status['services']['database'] = 'connected';
        } catch (\Exception $e) {
            $status['services']['database'] = 'disconnected';
            $status['status'] = 'degraded';
        }

        // Check Redis connection
        try {
            Redis::ping();
            $status['services']['redis'] = 'connected';
        } catch (\Exception $e) {
            $status['services']['redis'] = 'disconnected';
            $status['status'] = 'degraded';
        }

        $statusCode = $status['status'] === 'ok' ? 200 : 503;

        return response()->json($status, $statusCode);
    }
}
