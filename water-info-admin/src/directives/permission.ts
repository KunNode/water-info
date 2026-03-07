import type { Directive, DirectiveBinding } from 'vue'
import { useUserStore } from '@/stores/user'

export const permissionDirective: Directive = {
  mounted(el: HTMLElement, binding: DirectiveBinding<string | string[]>) {
    const userStore = useUserStore()
    const requiredRoles = Array.isArray(binding.value) ? binding.value : [binding.value]

    if (requiredRoles.length > 0 && !userStore.hasRole(requiredRoles)) {
      el.parentNode?.removeChild(el)
    }
  },
}
