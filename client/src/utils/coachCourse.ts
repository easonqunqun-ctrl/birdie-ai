/** M11-06 · 教练定制课程判定（created_by_user_id 非空）. */

import type { CourseRead } from '@/services/coursesService'

export function isCoachCustomCourse(course: CourseRead): boolean {
  return Boolean(course.created_by_user_id)
}
