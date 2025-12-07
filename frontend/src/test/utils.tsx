import React, { ReactElement } from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { KeyboardShortcutsProvider } from '../hooks/useKeyboardShortcuts';

// Create a fresh QueryClient for each test
function createTestQueryClient() {
    return new QueryClient({
        defaultOptions: {
            queries: {
                retry: false,
                gcTime: 0,
            },
            mutations: {
                retry: false,
            },
        },
    });
}

interface WrapperProps {
    children: React.ReactNode;
}

// Custom render function that wraps component with providers
function customRender(
    ui: ReactElement,
    options?: Omit<RenderOptions, 'wrapper'>
) {
    const queryClient = createTestQueryClient();

    function Wrapper({ children }: WrapperProps) {
        return (
            <QueryClientProvider client={queryClient}>
                <BrowserRouter>
                    <KeyboardShortcutsProvider>
                        {children}
                    </KeyboardShortcutsProvider>
                </BrowserRouter>
            </QueryClientProvider>
        );
    }

    return {
        ...render(ui, { wrapper: Wrapper, ...options }),
        queryClient,
    };
}

// Re-export everything from testing-library
 
export * from '@testing-library/react';
export { default as userEvent } from '@testing-library/user-event';
export { customRender as render };
