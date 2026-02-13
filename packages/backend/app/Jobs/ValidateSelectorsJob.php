<?php

namespace App\Jobs;

use App\Models\Task;
use App\Services\ScraperClient;
use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;
use Illuminate\Support\Facades\Log;

class ValidateSelectorsJob implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    /**
     * The number of times the job may be attempted.
     */
    public int $tries = 1;

    /**
     * The maximum number of seconds the job can run.
     */
    public int $timeout = 120;

    /**
     * Create a new job instance.
     */
    public function __construct(
        public Task $task,
    ) {}

    /**
     * Execute the job.
     */
    public function handle(ScraperClient $scraperClient): void
    {
        try {
            $this->task->load('formDefinitions.formFields');

            $selectors = [];
            foreach ($this->task->formDefinitions as $fd) {
                if ($fd->form_selector) {
                    $selectors[] = $fd->form_selector;
                }
                if ($fd->submit_selector) {
                    $selectors[] = $fd->submit_selector;
                }

                foreach ($fd->formFields as $field) {
                    $selectors[] = $field->field_selector;
                }
            }

            $result = $scraperClient->validateSelectors(
                url: $this->task->target_url,
                selectors: array_unique($selectors),
            );

            Log::info('Selector validation completed', [
                'task_id' => $this->task->id,
                'result' => $result,
            ]);

        } catch (\Exception $e) {
            Log::error('Selector validation failed', [
                'task_id' => $this->task->id,
                'error' => $e->getMessage(),
            ]);
        }
    }
}
