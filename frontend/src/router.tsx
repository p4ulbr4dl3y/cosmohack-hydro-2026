import { createBrowserRouter } from 'react-router-dom';
import { Landing } from './pages/Landing';
import { Dashboard } from './pages/Dashboard';
import { Report } from './pages/Report';
import { Compare } from './pages/Compare';
import { Methodology } from './pages/Methodology';
import { ApiDocs } from './pages/ApiDocs';
import { NotFound } from './pages/NotFound';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Landing />,
  },
  {
    path: '/dashboard',
    element: <Dashboard />,
  },
  {
    path: '/dashboard/:pairId',
    element: <Dashboard />,
  },
  {
    path: '/report/:pairId',
    element: <Report />,
  },
  {
    path: '/compare/:pairId',
    element: <Compare />,
  },
  {
    path: '/methodology',
    element: <Methodology />,
  },
  {
    path: '/api-docs',
    element: <ApiDocs />,
  },
  {
    path: '*',
    element: <NotFound />,
  },
]);
