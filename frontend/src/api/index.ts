import type { ClienteApi } from './contrato'
import { apiHttp } from './apiHttp'
import { apiMock } from './mock'

export const USAR_MOCK = import.meta.env.VITE_USAR_MOCK === 'true'

export const api: ClienteApi = USAR_MOCK ? apiMock : apiHttp

export type { ClienteApi }
