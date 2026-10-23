import useSWR, { SWRConfiguration } from 'swr';
import { api } from './api';

const defaultConfig: SWRConfiguration = {
  revalidateOnFocus: false,
  shouldRetryOnError: false,
  dedupingInterval: 2000,
};

export function useApi<T>(key: string | null, fetcher: () => Promise<T>, config?: SWRConfiguration) {
  const { data, error, isLoading, mutate } = useSWR<T>(key, fetcher, {
    ...defaultConfig,
    ...config,
  });

  return {
    data,
    error,
    isLoading,
    mutate,
    isError: !!error,
  };
}

export function useStats() {
  return useApi('stats', () => api.getStats());
}

export function useHealth() {
  return useApi('health', () => api.health(), { refreshInterval: 30000 });
}

export function useTransactions(limit = 100, offset = 0) {
  return useApi(`transactions-${limit}-${offset}`, () => api.listTransactions(limit, offset));
}

export function useTransaction(id: string | null) {
  return useApi(id ? `transaction-${id}` : null, () => api.getTransaction(id!), {
    revalidateOnMount: true,
  });
}

export function useCases() {
  return useApi('cases', () => api.listCases());
}

export function useCase(id: string | null) {
  return useApi(id ? `case-${id}` : null, () => api.getCase(id!));
}

export function useRules() {
  return useApi('rules', () => api.listRules());
}

export function useApiKeys() {
  return useApi('api-keys', () => api.listApiKeys());
}

export function useFilings(status?: string, filingType?: string) {
  const key = `filings-${status || 'all'}-${filingType || 'all'}`;
  return useApi(key, () => api.listFilings(status, filingType));
}
