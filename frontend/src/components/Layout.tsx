import { Outlet, NavLink } from 'react-router-dom'
import { Activity, LayoutDashboard, Heart, BarChart2 } from 'lucide-react'
import styles from './Layout.module.css'

export default function Layout() {
  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <div className={styles.logo}>
          <div className={styles.logoIcon}>
            <Activity size={14} strokeWidth={2.5} />
          </div>
          <span>IMS</span>
        </div>
        <div className={styles.sidebarBody}>
          <nav className={styles.nav}>
            <div className={styles.navSection}>
              <p className={styles.navLabel}>Monitor</p>
              <NavLink to="/dashboard"
                className={({ isActive }) => `${styles.navItem} ${isActive ? styles.active : ''}`}>
                <LayoutDashboard size={14} /><span>Dashboard</span>
              </NavLink>
              <NavLink to="/observability"
                className={({ isActive }) => `${styles.navItem} ${isActive ? styles.active : ''}`}>
                <BarChart2 size={14} /><span>Observability</span>
              </NavLink>
            </div>
            <div className={styles.navSection}>
              <p className={styles.navLabel}>System</p>
              <NavLink to="/health"
                className={({ isActive }) => `${styles.navItem} ${isActive ? styles.active : ''}`}>
                <Heart size={14} /><span>Health</span>
              </NavLink>
            </div>
          </nav>
        </div>
        <div className={styles.sidebarFooter}>
          <div className={styles.footerRow}>
            <span className={styles.version}>v1.0.0</span>
            <span className={styles.statusDot} title="System Online" />
          </div>
        </div>
      </aside>
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  )
}
