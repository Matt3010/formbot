<?php

namespace App\Http\Controllers;

use App\Http\Requests\AnalyzeUrlRequest;
use App\Models\Task;
use Illuminate\Http\JsonResponse;

class AnalyzerController extends Controller
{
    /**
     * Create a new task for VNC-based form editing.
     */
    public function analyze(AnalyzeUrlRequest $request): JsonResponse
    {
        $task = Task::create([
            'user_id' => auth()->id(),
            'name' => $request->input('name', 'New Task'),
            'target_url' => $request->input('url'),
            'current_editing_url' => $request->input('url'),
            'status' => 'editing',
            'editing_status' => 'idle',
            'editing_step' => 0,
            'user_corrections' => [
                'steps' => [[
                    'step_order' => 0,
                    'form_type' => 'target',
                    'form_selector' => '',
                    'submit_selector' => '',
                    'fields' => [],
                    'page_url' => $request->input('url'),
                ]],
            ],
        ]);

        return response()->json([
            'task_id' => $task->id,
            'message' => 'Task created. Open the VNC editor to configure fields.',
        ]);
    }
}
