import type { UserInfo } from '@/types'

const ADMIN_ROLES = ['ADMIN']
const OPERATOR_ROLES = ['ADMIN', 'OPERATOR']

export function hasRole(userRoles: string[], required: string | string[]): boolean {
  const requiredArr = Array.isArray(required) ? required : [required]
  return requiredArr.some((r) => userRoles.includes(r))
}

export function isAdmin(user: UserInfo | null): boolean {
  return !!user && hasRole(user.roles, ADMIN_ROLES)
}

export function isOperator(user: UserInfo | null): boolean {
  return !!user && hasRole(user.roles, OPERATOR_ROLES)
}

export function canAccess(userRoles: string[], requiredRoles?: string[]): boolean {
  if (!requiredRoles || requiredRoles.length === 0) return true
  return hasRole(userRoles, requiredRoles)
}
